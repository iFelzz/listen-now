"""
Listen Now – FastAPI Backend
────────────────────────────
Endpoints:
  GET  /                   → Serves the frontend (index.html)
  GET  /favicon.ico        → App favicon
  GET  /api/health         → Health check
  GET  /api/search         → Search YouTube (rate-limited: 30/min per IP)
  POST /api/download       → Download audio as MP3 (rate-limited: 10/min per IP)
  GET  /api/storage        → Storage usage info
  POST /api/cleanup        → Trigger manual cleanup
  GET  /downloads/{file}   → Serve the downloaded MP3 file

Stability features:
  - Rate limiting: 30/min search, 10/min download per IP (slowapi)
  - Audio quality options: 128 / 192 / 320 kbps
  - yt-dlp version check on startup
  - Concurrent download lock per filename (prevents race conditions)
  - Temp file cleanup on error (.part / .webm / .m4a)
  - Auto-cleanup: files deleted after MAX_AGE_HOURS (default 1h)
  - Folder size capped at MAX_STORAGE_MB (default 500 MB)
  - Cleanup runs every CLEANUP_INTERVAL_MINUTES (default 30 min)
"""

import os
import re
import time
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

import yt_dlp
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
# pyrefly: ignore [missing-import]
from slowapi import Limiter, _rate_limit_exceeded_handler
# pyrefly: ignore [missing-import]
from slowapi.util import get_remote_address
# pyrefly: ignore [missing-import]
from slowapi.errors import RateLimitExceeded
import shutil

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent
STATIC_DIR    = BASE_DIR / "static"
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

# ── FFmpeg detection ─────────────────────────────────────────
# Cari FFmpeg dari berbagai lokasi: bundled project, winget, PATH

def _find_ffmpeg() -> str | None:
    # 1. Bundled di dalam project (Windows)
    bundled = BASE_DIR / "ffmpeg" / "bin"
    if bundled.exists() and (bundled / "ffmpeg.exe").exists():
        return str(bundled)
    # 2. Winget install path
    winget_links = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"
    if (winget_links / "ffmpeg.exe").exists():
        return str(winget_links)
    # 3. System PATH (Linux/macOS/Windows)
    if shutil.which("ffmpeg"):
        return None  # None = yt-dlp pakai PATH otomatis
    return None

FFMPEG_LOCATION = _find_ffmpeg()
if FFMPEG_LOCATION:
    logger.info("FFmpeg found at: %s", FFMPEG_LOCATION)
else:
    if shutil.which("ffmpeg"):
        logger.info("FFmpeg found in system PATH")
    else:
        logger.warning("FFmpeg NOT found! Download conversion will fail.")

# ── Auto-cleanup config ───────────────────────────────────────
MAX_AGE_HOURS            = float(os.environ.get("MAX_AGE_HOURS",    "1"))   # delete files older than 1 hour
MAX_STORAGE_MB           = float(os.environ.get("MAX_STORAGE_MB",   "500")) # cap folder at 500 MB
CLEANUP_INTERVAL_MINUTES = float(os.environ.get("CLEANUP_INTERVAL", "30"))  # run every 30 minutes

# ── Concurrent download locks ─────────────────────────────────
# Prevents race conditions when multiple users download the same file
_download_locks: dict[str, asyncio.Lock] = {}

# ── Preview URL cache (TTL = 10 minutes) ──────────────────────
# Avoids re-calling yt-dlp every time user clicks Play on the same song
_preview_cache: dict[str, dict] = {}
_PREVIEW_TTL_SECONDS = 600  # 10 minutes

# ── Search results cache (TTL = 5 minutes) ──────────────────────
# Avoids redundant yt-dlp calls for repeated identical searches
_search_cache: dict[str, dict] = {}
_SEARCH_TTL_SECONDS = 300  # 5 minutes


# ── Cleanup logic ─────────────────────────────────────────────
def run_cleanup() -> dict:
    """
    Delete MP3 files in downloads/ that:
    1. Berumur lebih dari MAX_AGE_HOURS, ATAU
    2. Exceed MAX_STORAGE_MB (delete oldest files first)
    Mengembalikan ringkasan hasil cleanup.
    """
    now        = time.time()
    max_age_s  = MAX_AGE_HOURS * 3600
    max_bytes  = MAX_STORAGE_MB * 1024 * 1024
    deleted    = []
    errors     = []

    # Ambil semua file MP3, urutkan dari terlama
    files = sorted(
        [f for f in DOWNLOADS_DIR.iterdir() if f.is_file() and f.suffix.lower() == ".mp3"],
        key=lambda f: f.stat().st_mtime
    )

    # 1. Delete expired files
    for f in files[:]:
        try:
            age = now - f.stat().st_mtime
            if age > max_age_s:
                size_mb = f.stat().st_size / 1024 / 1024
                f.unlink()
                deleted.append(f.name)
                files.remove(f)
                logger.info("Cleanup [expired]: %s (%.1f MB, %.0f menit)", f.name, size_mb, age/60)
        except Exception as e:
            errors.append(str(e))

    # 2. Delete oldest files if folder is still too large
    total = sum(f.stat().st_size for f in files if f.exists())
    while total > max_bytes and files:
        oldest = files.pop(0)
        try:
            size = oldest.stat().st_size
            oldest.unlink()
            deleted.append(oldest.name)
            total -= size
            logger.info("Cleanup [size-limit]: %s (total %.1f MB)", oldest.name, total/1024/1024)
        except Exception as e:
            errors.append(str(e))

    total_mb = sum(f.stat().st_size for f in DOWNLOADS_DIR.iterdir()
                   if f.is_file()) / 1024 / 1024
    logger.info("Cleanup finished: %d deleted, folder size %.1f MB", len(deleted), total_mb)
    return {"deleted": deleted, "errors": errors, "folder_mb": round(total_mb, 2)}


async def _cleanup_loop():
    """Background task: jalankan cleanup secara berkala."""
    interval = CLEANUP_INTERVAL_MINUTES * 60
    logger.info(
        "Auto-cleanup active: max_age=%.0fh, max_size=%.0fMB, interval=%.0f min",
        MAX_AGE_HOURS, MAX_STORAGE_MB, CLEANUP_INTERVAL_MINUTES
    )
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(run_cleanup)
        except Exception as exc:
            logger.error("Cleanup error: %s", exc)


# ── Lifespan (startup / shutdown) ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Check yt-dlp version
    try:
        ver = yt_dlp.version.__version__
        logger.info("yt-dlp version: %s", ver)
        # Parse date from version string like "2024.11.4"
        parts = str(ver).split(".")
        if len(parts) == 3:
            import datetime
            ver_date = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            age_days = (datetime.date.today() - ver_date).days
            if age_days > 30:
                logger.warning(
                    "yt-dlp is %d days old (version %s). "
                    "Run: venv\\Scripts\\pip install -U yt-dlp",
                    age_days, ver
                )
    except Exception:
        logger.warning("Could not determine yt-dlp version.")

    # 2. Run initial cleanup then start background loop
    await asyncio.to_thread(run_cleanup)
    task = asyncio.create_task(_cleanup_loop())
    yield
    # Shutdown
    task.cancel()

# ── Rate limiter ─────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/day"])

# ── FastAPI app ──────────────────────────────────────────────
app = FastAPI(
    title="Listen Now",
    description="YouTube MP3 Downloader API powered by yt-dlp",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Serve downloads folder
app.mount("/downloads", StaticFiles(directory=str(DOWNLOADS_DIR)), name="downloads")


# ── WebSockets / Progress Tracking ───────────────────────────
_progress_data = {}

@app.websocket("/api/ws/progress/{client_id}")
async def websocket_progress(websocket: WebSocket, client_id: str):
    await websocket.accept()
    try:
        last_sent = None
        while True:
            data = _progress_data.get(client_id)
            if data and data != last_sent:
                await websocket.send_json(data)
                last_sent = data
            await asyncio.sleep(0.4)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning(f"WebSocket error for {client_id}: {exc}")
    finally:
        _progress_data.pop(client_id, None)


# ── Pydantic Models ──────────────────────────────────────────
ALLOWED_QUALITIES = {"128", "192", "320"}

class SearchRequest(BaseModel):
    query: str

class DownloadRequest(BaseModel):
    url:     str
    title:   Optional[str] = "audio"
    quality: Optional[str] = "192"   # kbps: 128 | 192 | 320
    client_id: Optional[str] = None

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: str) -> str:
        if v not in ALLOWED_QUALITIES:
            raise ValueError(f"quality must be one of {sorted(ALLOWED_QUALITIES)}")
        return v


# ── Helper: sanitise filename ─────────────────────────────────
def sanitise_filename(name: str) -> str:
    """
    Clean filename of illegal Windows/Linux characters.
    Spaces are preserved for readability.
    Illegal characters: \\ / * ? : " < > |
    """
    # Remove invalid Windows/Linux filename characters
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    # Strip excess spaces and collapse double spaces
    name = re.sub(r"\s+", " ", name).strip()
    return name[:200]  # cap length


def _cleanup_temp_files(title: str) -> None:
    """
    Remove leftover temporary files created by yt-dlp when a download fails.
    Matches any file in downloads/ whose stem starts with the given title,
    excluding already-completed .mp3 files.
    """
    TEMP_EXTS = {".part", ".ytdl", ".webm", ".m4a", ".opus", ".3gp"}
    for f in DOWNLOADS_DIR.iterdir():
        if f.is_file() and f.stem.startswith(title) and f.suffix.lower() in TEMP_EXTS:
            try:
                f.unlink()
                logger.info("Cleaned up temp file: %s", f.name)
            except Exception as e:
                logger.warning("Failed to remove temp file %s: %s", f.name, e)


# ── Routes ───────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    """Serve the main frontend page."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found.")
    return FileResponse(str(index_path))


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve app favicon to prevent 404 errors in browser console."""
    favicon_path = STATIC_DIR / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(str(favicon_path))
    # Fallback: serve logo.png as favicon
    logo_path = STATIC_DIR / "logo.png"
    if logo_path.exists():
        return FileResponse(str(logo_path), media_type="image/png")
    raise HTTPException(status_code=404, detail="Favicon not found.")


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "Listen Now"}


@app.get("/api/storage")
async def storage_info():
    """Storage usage info for downloads/ and cleanup config."""
    files = [
        f for f in DOWNLOADS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() == ".mp3"
    ]
    now = time.time()
    file_list = sorted(
        [
            {
                "filename": f.name,
                "size_mb":  round(f.stat().st_size / 1024 / 1024, 2),
                "age_minutes": round((now - f.stat().st_mtime) / 60, 1),
            }
            for f in files
        ],
        key=lambda x: x["age_minutes"],
        reverse=True,
    )
    total_mb = sum(f["size_mb"] for f in file_list)
    return JSONResponse(content={
        "total_files":  len(file_list),
        "total_mb":     round(total_mb, 2),
        "max_age_hours":    MAX_AGE_HOURS,
        "max_storage_mb":   MAX_STORAGE_MB,
        "cleanup_interval_minutes": CLEANUP_INTERVAL_MINUTES,
        "files": file_list,
    })


@app.post("/api/cleanup")
async def manual_cleanup():
    """Trigger cleanup manual — hapus file kadaluarsa dan cek batas storage."""
    result = await asyncio.to_thread(run_cleanup)
    return JSONResponse(content={"success": True, **result})


@app.get("/api/search")
@limiter.limit("30/minute")
async def search(request: Request, q: str, limit: int = 6):
    """
    Search YouTube and return up to `limit` results.
    
    Query params:
      q     – search query string
      limit – number of results (default 6, max 50)
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required.")

    limit = min(max(1, limit), 50)

    ydl_opts = {
        "quiet":        True,
        "no_warnings":  True,
        "extract_flat": True,   # metadata only, no download
        "skip_download": True,
        "noplaylist":   True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    q_stripped = q.strip()
    is_url = q_stripped.startswith("http://") or q_stripped.startswith("https://")
    search_query = q_stripped if is_url else f"ytsearch{limit}:{q_stripped}"

    # ── Check search cache (skip for direct URLs — those are always fresh) ──
    cache_key = f"{q_stripped.lower()}::{limit}"
    if not is_url:
        cached = _search_cache.get(cache_key)
        if cached and (time.time() - cached["ts"]) < _SEARCH_TTL_SECONDS:
            logger.info("Search cache hit for: %s (limit=%d)", q_stripped, limit)
            return JSONResponse(content={"results": cached["results"]})

    logger.info("Processing query (is_url=%s): %s", is_url, q)

    try:
        def _search():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(search_query, download=False)

        info = await asyncio.to_thread(_search)

        if not info:
            return JSONResponse(content={"results": []})
        
        # If it's a direct video URL, info is the video dict itself, not a list of entries
        entries = info.get("entries") if "entries" in info else [info]

        results = []
        for entry in entries:
            if not entry:
                continue
            duration_sec = entry.get("duration") or 0
            minutes, seconds = divmod(int(duration_sec), 60)
            results.append({
                "id":        entry.get("id", ""),
                "url":       f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                "title":     entry.get("title", "Unknown Title"),
                "channel":   entry.get("uploader") or entry.get("channel", "Unknown"),
                "duration":  f"{minutes}:{seconds:02d}",
                "thumbnail": entry.get("thumbnail")
                             or f"https://i.ytimg.com/vi/{entry.get('id', '')}/hqdefault.jpg",
                "views":     entry.get("view_count", 0),
            })

        logger.info("Found %d results for query: %s", len(results), q)

        # ── Store in search cache (only for keyword searches, not direct URLs) ──
        if not is_url:
            _search_cache[cache_key] = {"results": results, "ts": time.time()}

        return JSONResponse(content={"results": results})

    except yt_dlp.utils.DownloadError as exc:
        logger.error("yt-dlp DownloadError: %s", exc)
        raise HTTPException(status_code=502, detail=f"YouTube search failed: {str(exc)}")
    except Exception as exc:
        logger.exception("Unexpected error during search")
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/preview")
@limiter.limit("20/minute")
async def preview(request: Request, url: str):
    """
    Extract best audio stream URL for preview playback.
    Results are cached in-memory for up to 10 minutes to avoid
    redundant yt-dlp calls when a user replays the same song.
    """
    if not url.strip():
        raise HTTPException(status_code=400, detail="URL is required")

    # ── Check in-memory cache first ────────────────────────────
    cached = _preview_cache.get(url)
    if cached and (time.time() - cached["ts"]) < _PREVIEW_TTL_SECONDS:
        logger.info("Preview cache hit: %s", url)
        return {"stream_url": cached["stream_url"]}

    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "source_address": "0.0.0.0",
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    try:
        def _extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        info = await asyncio.to_thread(_extract)
        stream_url = info.get("url")
        if not stream_url:
            raise HTTPException(status_code=404, detail="Stream URL not found")

        # ── Store in cache ──────────────────────────────────────
        _preview_cache[url] = {"stream_url": stream_url, "ts": time.time()}
        logger.info("Preview extracted and cached: %s", url)

        return {"stream_url": stream_url}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Preview extraction error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to extract preview: {str(exc)}")


@app.get("/api/file/{filename}", include_in_schema=False)
async def serve_file(filename: str, name: Optional[str] = None):
    """
    Serve a downloaded file with an optional clean display name.
    The `name` query param sets the Content-Disposition filename shown to the user,
    allowing internal files to use quality-tagged names while downloads appear clean.
    """
    file_path = DOWNLOADS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    display_name = name or filename
    return FileResponse(
        str(file_path),
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="{display_name}"'},
    )


@app.post("/api/download")
@limiter.limit("10/minute")
async def download(request: Request, body: DownloadRequest, background_tasks: BackgroundTasks):
    """
    Download audio from the given YouTube URL and convert to MP3.
    Supports quality: 128 / 192 / 320 kbps (default: 192).
    Rate-limited to 10 requests per minute per IP.

    Internal cache filename includes quality suffix (e.g. Title_192k.mp3) to ensure
    different qualities are cached separately. However, the file is served to the
    browser with a clean name (Title.mp3) via Content-Disposition in /api/file/.

    Uses per-filename async lock to prevent race conditions when multiple
    users request the same song simultaneously.
    """
    url     = body.url.strip()
    title   = sanitise_filename(body.title or "audio")
    quality = body.quality or "192"

    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")

    # Internal file includes quality tag for correct per-quality caching.
    # The clean name (without quality) is used as the display name for the user.
    cache_filename = f"{title}_{quality}k.mp3"
    clean_filename = f"{title}.mp3"
    output_path    = DOWNLOADS_DIR / cache_filename

    # If file already exists (cache hit), serve it immediately
    if output_path.exists():
        logger.info("Cache hit – serving existing file: %s", cache_filename)
        return JSONResponse(content={
            "success":      True,
            "filename":     cache_filename,
            "download_url": f"/api/file/{cache_filename}?name={clean_filename}",
        })

    # ── Acquire per-filename lock ─────────────────────────────
    # Ensures only one download process runs per unique cache filename.
    # Other requests for the same file+quality will wait and reuse the result.
    if cache_filename not in _download_locks:
        _download_locks[cache_filename] = asyncio.Lock()
    lock = _download_locks[cache_filename]

    client_id = body.client_id

    try:
        async with lock:
            # Re-check after acquiring lock — another coroutine may have finished
            if output_path.exists():
                logger.info("Cache hit (post-lock) – serving: %s", cache_filename)
                return JSONResponse(content={
                    "success":      True,
                    "filename":     cache_filename,
                    "download_url": f"/api/file/{cache_filename}?name={clean_filename}",
                })

            def progress_hook(d):
                if not client_id:
                    return
                if d['status'] == 'downloading':
                    percent_str = d.get('_percent_str', '0%')
                    # Remove ANSI escape codes that yt-dlp might output
                    percent_str = re.sub(r'\x1b[^m]*m', '', percent_str).strip()
                    _progress_data[client_id] = {"status": "downloading", "percent": percent_str}
                elif d['status'] == 'finished':
                    _progress_data[client_id] = {"status": "converting", "percent": "100%"}

            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": str(DOWNLOADS_DIR / f"{title}.%(ext)s"),
                "quiet":        True,
                "no_warnings":  True,
                "noplaylist":   True,
                "prefer_ffmpeg": True,
                "source_address": "0.0.0.0", # Force IPv4 to prevent hanging on datacenter servers
                "progress_hooks": [progress_hook] if client_id else [],
                "writethumbnail": True,
                # Use bundled FFmpeg if available, else fall back to system PATH
                **(({"ffmpeg_location": FFMPEG_LOCATION}) if FFMPEG_LOCATION else {}),
                "http_headers": {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android", "web"],
                    }
                },
                "postprocessors": [
                    {
                        "key":              "FFmpegExtractAudio",
                        "preferredcodec":   "mp3",
                        "preferredquality": quality,
                    },
                    {"key": "FFmpegMetadata", "add_metadata": True},
                    {"key": "EmbedThumbnail", "already_have_thumbnail": False},
                ],
            }

            logger.info("Downloading: %s → %s", url, cache_filename)

            try:
                def _download():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])

                await asyncio.to_thread(_download)

                # yt-dlp writes the file as Title.mp3 (from outtmpl); rename to cache_filename
                default_output = DOWNLOADS_DIR / f"{title}.mp3"
                if default_output.exists() and not output_path.exists():
                    default_output.rename(output_path)

                if not output_path.exists():
                    raise HTTPException(
                        status_code=500,
                        detail="Download completed but output file not found on disk.",
                    )

                logger.info("Download successful: %s", cache_filename)
                return JSONResponse(content={
                    "success":      True,
                    "filename":     cache_filename,
                    "download_url": f"/api/file/{cache_filename}?name={clean_filename}",
                })

            except yt_dlp.utils.DownloadError as exc:
                logger.error("yt-dlp DownloadError: %s", exc)
                _cleanup_temp_files(title)
                raise HTTPException(status_code=502, detail=f"Download failed: {str(exc)}")
            except HTTPException:
                _cleanup_temp_files(title)
                raise
            except Exception as exc:
                logger.exception("Unexpected error during download")
                _cleanup_temp_files(title)
                raise HTTPException(status_code=500, detail=str(exc))

    finally:
        # Always clean up the lock entry after the download attempt completes,
        # regardless of success or failure, to prevent unbounded dict growth.
        _download_locks.pop(cache_filename, None)


# ── Entry point (local dev) ──────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
