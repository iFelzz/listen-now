"""
Listen Now – FastAPI Backend
────────────────────────────
Endpoints:
  GET  /                   → Serves the frontend (index.html)
  GET  /favicon.ico        → App favicon
  GET  /api/health         → Health check
  GET  /api/search         → Search YouTube (returns up to 6 results)
  POST /api/download       → Download audio as MP3 (192 kbps)
  GET  /api/storage        → Storage usage info
  POST /api/cleanup        → Trigger manual cleanup
  GET  /downloads/{file}   → Serve the downloaded MP3 file

Stability features:
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
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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


# ── Cleanup logic ─────────────────────────────────────────────
def run_cleanup() -> dict:
    """
    Hapus file MP3 di downloads/ yang:
    1. Berumur lebih dari MAX_AGE_HOURS, ATAU
    2. Folder melebihi MAX_STORAGE_MB (hapus file terlama dulu)
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

    # 1. Hapus file yang sudah kadaluarsa
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

    # 2. Hapus file terlama jika folder masih terlalu besar
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
    logger.info("Cleanup selesai: %d dihapus, folder %.1f MB", len(deleted), total_mb)
    return {"deleted": deleted, "errors": errors, "folder_mb": round(total_mb, 2)}


async def _cleanup_loop():
    """Background task: jalankan cleanup secara berkala."""
    interval = CLEANUP_INTERVAL_MINUTES * 60
    logger.info(
        "Auto-cleanup aktif: max_age=%.0fj, max_size=%.0fMB, interval=%.0f menit",
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
    # Startup: jalankan cleanup sekali lalu loop berkala
    await asyncio.to_thread(run_cleanup)
    task = asyncio.create_task(_cleanup_loop())
    yield
    # Shutdown
    task.cancel()

# ── FastAPI app ──────────────────────────────────────────────
app = FastAPI(
    title="Listen Now",
    description="YouTube MP3 Downloader API powered by yt-dlp",
    version="1.0.0",
    lifespan=lifespan,
)

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


# ── Pydantic Models ──────────────────────────────────────────
class DownloadRequest(BaseModel):
    url: str
    title: Optional[str] = "audio"


# ── Helper: sanitise filename ─────────────────────────────────
def sanitise_filename(name: str) -> str:
    """
    Bersihkan nama file dari karakter ilegal Windows/Linux.
    Spasi dipertahankan agar nama file tetap rapi dan mudah dibaca.
    Karakter ilegal: \\ / * ? : " < > |
    """
    # Hapus karakter yang tidak valid di nama file Windows/Linux
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    # Hilangkan spasi berlebih di awal/akhir dan kolapskan spasi ganda
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
    """Info penggunaan folder downloads/ dan konfigurasi cleanup."""
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
async def search(q: str, limit: int = 6):
    """
    Search YouTube and return up to `limit` results.
    
    Query params:
      q     – search query string
      limit – number of results (default 6, max 10)
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required.")

    limit = min(max(1, limit), 10)

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

    search_query = f"ytsearch{limit}:{q.strip()}"
    logger.info("Searching YouTube for: %s", q)

    try:
        def _search():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(search_query, download=False)

        info = await asyncio.to_thread(_search)

        if not info or "entries" not in info:
            return JSONResponse(content={"results": []})

        results = []
        for entry in info["entries"]:
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
        return JSONResponse(content={"results": results})

    except yt_dlp.utils.DownloadError as exc:
        logger.error("yt-dlp DownloadError: %s", exc)
        raise HTTPException(status_code=502, detail=f"YouTube search failed: {str(exc)}")
    except Exception as exc:
        logger.exception("Unexpected error during search")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/download")
async def download(request: DownloadRequest, background_tasks: BackgroundTasks):
    """
    Download audio from the given YouTube URL and convert to MP3 (192 kbps).
    Returns a JSON with the download URL once the file is ready.

    Uses per-filename async lock to prevent race conditions when multiple
    users request the same song simultaneously.
    """
    url   = request.url.strip()
    title = sanitise_filename(request.title or "audio")

    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")

    output_filename = f"{title}.mp3"
    output_path     = DOWNLOADS_DIR / output_filename

    # If file already exists, serve it immediately (no lock needed)
    if output_path.exists():
        logger.info("Cache hit – serving existing file: %s", output_filename)
        return JSONResponse(content={
            "success":      True,
            "filename":     output_filename,
            "download_url": f"/downloads/{output_filename}",
        })

    # ── Acquire per-filename lock ─────────────────────────────
    # Ensures only one download process runs per unique filename.
    # Other requests for the same file will wait and reuse the result.
    if output_filename not in _download_locks:
        _download_locks[output_filename] = asyncio.Lock()
    lock = _download_locks[output_filename]

    async with lock:
        # Re-check after acquiring lock — another coroutine may have finished
        if output_path.exists():
            logger.info("Cache hit (post-lock) – serving: %s", output_filename)
            return JSONResponse(content={
                "success":      True,
                "filename":     output_filename,
                "download_url": f"/downloads/{output_filename}",
            })

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(DOWNLOADS_DIR / f"{title}.%(ext)s"),
            "quiet":        True,
            "no_warnings":  True,
            "noplaylist":   True,
            "prefer_ffmpeg": True,
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
                    "preferredquality": "192",
                },
                {
                    "key":          "FFmpegMetadata",
                    "add_metadata": True,
                },
            ],
        }

        logger.info("Downloading: %s → %s", url, output_filename)

        try:
            def _download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

            await asyncio.to_thread(_download)

            if not output_path.exists():
                raise HTTPException(
                    status_code=500,
                    detail="Download completed but output file not found on disk.",
                )

            logger.info("Download successful: %s", output_filename)
            return JSONResponse(content={
                "success":      True,
                "filename":     output_filename,
                "download_url": f"/downloads/{output_filename}",
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
            # Remove lock entry once no longer needed
            _download_locks.pop(output_filename, None)


# ── Entry point (local dev) ──────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
