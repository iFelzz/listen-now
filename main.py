"""
Listen Now – FastAPI Backend
────────────────────────────
Endpoints:
  GET  /                   → Serves the frontend (index.html)
  GET  /favicon.ico        → App favicon
  GET  /api/health         → Health check
  GET  /api/search         → Search YouTube (rate-limited: 30/min per IP)
  GET  /api/preview        → Stream audio preview (rate-limited: 20/min per IP)
  POST /api/download       → Download audio as MP3 (rate-limited: 10/min per IP)
  GET  /api/storage        → Storage usage info
  POST /api/cleanup        → Trigger manual cleanup
  GET  /api/file/{file}    → Serve the downloaded MP3 file safely
  WS   /api/ws/progress/{id} → Live download/convert progress

Stability & Security features:
  - Reference-counted async locking per file to prevent duplicate downloads
  - Path-traversal proof file delivery
  - Direct outtmpl naming preventing bitrate collisions
  - In-memory cache size capping and TTL eviction
  - Background auto-cleanup of expired and oversized downloads
  - Optional proxy & cookies.txt support for YouTube bot-detection bypass
  - Rate limiting via slowapi
"""

import os
import re
import time
import asyncio
import logging
import urllib.parse
import shutil
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

import yt_dlp
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

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

# ── Environment & External Config ────────────────────────────
MAX_AGE_HOURS            = float(os.environ.get("MAX_AGE_HOURS",    "1"))    # delete files older than 1 hour
MAX_STORAGE_MB           = float(os.environ.get("MAX_STORAGE_MB",   "500"))  # cap folder at 500 MB
CLEANUP_INTERVAL_MINUTES = float(os.environ.get("CLEANUP_INTERVAL", "30"))   # run every 30 minutes
CLEANUP_TOKEN            = os.environ.get("CLEANUP_TOKEN")                   # optional secret token for /api/cleanup
YTDLP_PROXY              = os.environ.get("YTDLP_PROXY")                     # optional proxy URL

# Cookies detection (from env or cookies.txt in root)
COOKIES_FILE = os.environ.get("YTDLP_COOKIES_FILE")
if not COOKIES_FILE and (BASE_DIR / "cookies.txt").exists():
    COOKIES_FILE = str(BASE_DIR / "cookies.txt")

if COOKIES_FILE:
    logger.info("Using yt-dlp cookies from: %s", COOKIES_FILE)
if YTDLP_PROXY:
    logger.info("Using yt-dlp proxy: %s", YTDLP_PROXY)

# ── FFmpeg detection ─────────────────────────────────────────
def _find_ffmpeg() -> str | None:
    # 1. Bundled inside project (Windows)
    bundled = BASE_DIR / "ffmpeg" / "bin"
    if bundled.exists() and (bundled / "ffmpeg.exe").exists():
        return str(bundled)
    # 2. Winget install path
    winget_links = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"
    if (winget_links / "ffmpeg.exe").exists():
        return str(winget_links)
    # 3. System PATH (Linux/macOS/Windows)
    if shutil.which("ffmpeg"):
        return None  # None = yt-dlp uses PATH automatically
    return None

FFMPEG_LOCATION = _find_ffmpeg()
if FFMPEG_LOCATION:
    logger.info("FFmpeg found at: %s", FFMPEG_LOCATION)
else:
    if shutil.which("ffmpeg"):
        logger.info("FFmpeg found in system PATH")
    else:
        logger.warning("FFmpeg NOT found! Download conversion will fail.")

def _get_base_ytdl_opts() -> dict[str, Any]:
    """Return common base options for yt-dlp extractors."""
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "source_address": "0.0.0.0",  # Force IPv4 to prevent hanging on datacenter servers
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }
    if FFMPEG_LOCATION:
        opts["ffmpeg_location"] = FFMPEG_LOCATION
    if COOKIES_FILE:
        opts["cookiefile"] = COOKIES_FILE
    if YTDLP_PROXY:
        opts["proxy"] = YTDLP_PROXY
    return opts

# ── Concurrent download locks (Ref-counted) ───────────────────
class DownloadLockRegistry:
    """
    Reference-counted async lock manager.
    Prevents race conditions while guaranteeing locks are safely
    preserved until all queued requests for the same file finish.
    """
    def __init__(self):
        self._locks: dict[str, asyncio.Lock] = {}
        self._refs: dict[str, int] = {}
        self._mutex = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, key: str):
        async with self._mutex:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
                self._refs[key] = 0
            self._refs[key] += 1
            lock = self._locks[key]

        try:
            async with lock:
                yield
        finally:
            async with self._mutex:
                self._refs[key] -= 1
                if self._refs[key] <= 0:
                    self._locks.pop(key, None)
                    self._refs.pop(key, None)

_download_lock_registry = DownloadLockRegistry()

# ── In-Memory Caches & TTL Eviction ───────────────────────────
_preview_cache: dict[str, dict] = {}
_PREVIEW_TTL_SECONDS = 600   # 10 minutes

_search_cache: dict[str, dict] = {}
_SEARCH_TTL_SECONDS = 300    # 5 minutes

_MAX_CACHE_ENTRIES = 300

def prune_memory_caches() -> None:
    """Evict expired entries and enforce size limits on memory caches."""
    now = time.time()

    # 1. Prune search cache
    expired_search = [k for k, v in _search_cache.items() if (now - v.get("ts", 0)) > _SEARCH_TTL_SECONDS]
    for k in expired_search:
        _search_cache.pop(k, None)
    if len(_search_cache) > _MAX_CACHE_ENTRIES:
        oldest_search = sorted(_search_cache.keys(), key=lambda k: _search_cache[k].get("ts", 0))
        for k in oldest_search[: len(_search_cache) - _MAX_CACHE_ENTRIES]:
            _search_cache.pop(k, None)

    # 2. Prune preview cache
    expired_preview = [k for k, v in _preview_cache.items() if (now - v.get("ts", 0)) > _PREVIEW_TTL_SECONDS]
    for k in expired_preview:
        _preview_cache.pop(k, None)
    if len(_preview_cache) > _MAX_CACHE_ENTRIES:
        oldest_preview = sorted(_preview_cache.keys(), key=lambda k: _preview_cache[k].get("ts", 0))
        for k in oldest_preview[: len(_preview_cache) - _MAX_CACHE_ENTRIES]:
            _preview_cache.pop(k, None)

# ── Cleanup logic ─────────────────────────────────────────────
def run_cleanup() -> dict:
    """
    Delete MP3 files in downloads/ that:
    1. Are older than MAX_AGE_HOURS, OR
    2. Exceed MAX_STORAGE_MB (delete oldest files first)
    Also cleans up in-memory caches.
    """
    now       = time.time()
    max_age_s = MAX_AGE_HOURS * 3600
    max_bytes = MAX_STORAGE_MB * 1024 * 1024
    deleted   = []
    errors    = []

    # Prune memory caches
    prune_memory_caches()

    # Get all MP3 files sorted from oldest to newest
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
                logger.info("Cleanup [expired]: %s (%.1f MB, %.0f min)", f.name, size_mb, age / 60)
        except Exception as e:
            errors.append(str(e))

    # 2. Delete oldest files if folder still exceeds MAX_STORAGE_MB
    total = sum(f.stat().st_size for f in files if f.exists())
    while total > max_bytes and files:
        oldest = files.pop(0)
        try:
            size = oldest.stat().st_size
            oldest.unlink()
            deleted.append(oldest.name)
            total -= size
            logger.info("Cleanup [size-limit]: %s (total %.1f MB)", oldest.name, total / 1024 / 1024)
        except Exception as e:
            errors.append(str(e))

    total_mb = sum(f.stat().st_size for f in DOWNLOADS_DIR.iterdir() if f.is_file()) / 1024 / 1024
    logger.info("Cleanup finished: %d deleted, folder size %.1f MB", len(deleted), total_mb)
    return {"deleted": deleted, "errors": errors, "folder_mb": round(total_mb, 2)}

async def _cleanup_loop():
    """Background task: periodically run storage & memory cleanup."""
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
        parts = str(ver).split(".")
        if len(parts) >= 3:
            import datetime
            ver_date = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            age_days = (datetime.date.today() - ver_date).days
            if age_days > 30:
                logger.warning(
                    "yt-dlp is %d days old (version %s). Update recommended: pip install -U yt-dlp",
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
    version="1.1.0",
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

# ── WebSockets / Progress Tracking ───────────────────────────
_progress_data: dict[str, dict] = {}

async def _delayed_progress_cleanup(client_id: str, delay: float = 10.0):
    """Remove progress tracking entry after delay to prevent memory leak."""
    await asyncio.sleep(delay)
    _progress_data.pop(client_id, None)

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
        logger.warning("WebSocket error for %s: %s", client_id, exc)
    finally:
        _progress_data.pop(client_id, None)

# ── Pydantic Models ──────────────────────────────────────────
ALLOWED_QUALITIES = {"128", "192", "320"}

class SearchRequest(BaseModel):
    query: str

class DownloadRequest(BaseModel):
    url:       str
    title:     Optional[str] = "audio"
    quality:   Optional[str] = "192"   # kbps: 128 | 192 | 320
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
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:200] if name else "audio"

def _cleanup_temp_files(stem_prefix: str) -> None:
    """
    Remove leftover temporary files created by yt-dlp on failure.
    Matches any file in downloads/ whose stem starts with stem_prefix.
    """
    TEMP_EXTS = {".part", ".ytdl", ".webm", ".m4a", ".opus", ".3gp"}
    for f in DOWNLOADS_DIR.iterdir():
        if f.is_file() and f.stem.startswith(stem_prefix) and f.suffix.lower() in TEMP_EXTS:
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
    """Serve app favicon."""
    favicon_path = STATIC_DIR / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(str(favicon_path))
    logo_path = STATIC_DIR / "logo.png"
    if logo_path.exists():
        return FileResponse(str(logo_path), media_type="image/png")
    raise HTTPException(status_code=404, detail="Favicon not found.")

@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "Listen Now", "version": "1.1.0"}

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
async def manual_cleanup(request: Request, x_token: Optional[str] = Header(None, alias="X-Cleanup-Token")):
    """
    Trigger manual cleanup.
    Protected by CLEANUP_TOKEN if configured in environment.
    """
    if CLEANUP_TOKEN:
        token_param = request.query_params.get("token")
        if x_token != CLEANUP_TOKEN and token_param != CLEANUP_TOKEN:
            raise HTTPException(status_code=403, detail="Unauthorized: invalid cleanup token.")

    result = await asyncio.to_thread(run_cleanup)
    return JSONResponse(content={"success": True, **result})

@app.get("/api/search")
@limiter.limit("30/minute")
async def search(request: Request, q: str, limit: int = 10):
    """
    Search YouTube and return up to `limit` results.
    Rate-limited: 30 requests/minute.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required.")

    limit = min(max(1, limit), 50)
    q_stripped = q.strip()
    is_url = q_stripped.startswith("http://") or q_stripped.startswith("https://")
    search_query = q_stripped if is_url else f"ytsearch{limit}:{q_stripped}"

    # Check search cache
    cache_key = f"{q_stripped.lower()}::{limit}"
    if not is_url:
        cached = _search_cache.get(cache_key)
        if cached and (time.time() - cached["ts"]) < _SEARCH_TTL_SECONDS:
            logger.info("Search cache hit for: %s (limit=%d)", q_stripped, limit)
            return JSONResponse(content={"results": cached["results"]})

    ydl_opts = {
        **_get_base_ytdl_opts(),
        "extract_flat": True,   # metadata only
        "skip_download": True,
    }

    logger.info("Processing query (is_url=%s): %s", is_url, q)

    try:
        def _search():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(search_query, download=False)

        info = await asyncio.to_thread(_search)

        if not info:
            return JSONResponse(content={"results": []})

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
                "thumbnail": entry.get("thumbnail") or f"https://i.ytimg.com/vi/{entry.get('id', '')}/hqdefault.jpg",
                "views":     entry.get("view_count", 0),
            })

        logger.info("Found %d results for query: %s", len(results), q)

        if not is_url:
            if len(_search_cache) >= _MAX_CACHE_ENTRIES:
                prune_memory_caches()
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
    Cached for up to 10 minutes.
    """
    if not url.strip():
        raise HTTPException(status_code=400, detail="URL is required")

    cached = _preview_cache.get(url)
    if cached and (time.time() - cached["ts"]) < _PREVIEW_TTL_SECONDS:
        logger.info("Preview cache hit: %s", url)
        return {"stream_url": cached["stream_url"]}

    ydl_opts = {
        **_get_base_ytdl_opts(),
        "format": "bestaudio/best",
    }

    try:
        def _extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        info = await asyncio.to_thread(_extract)
        stream_url = info.get("url")
        if not stream_url:
            raise HTTPException(status_code=404, detail="Stream URL not found")

        if len(_preview_cache) >= _MAX_CACHE_ENTRIES:
            prune_memory_caches()
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
    Serve a downloaded MP3 file safely.
    Strictly prevents path traversal and only serves valid .mp3 files.
    """
    safe_filename = Path(filename).name
    file_path = (DOWNLOADS_DIR / safe_filename).resolve()
    downloads_root = DOWNLOADS_DIR.resolve()

    try:
        if not file_path.is_relative_to(downloads_root) or not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found.")
    except (ValueError, RuntimeError):
        raise HTTPException(status_code=404, detail="Invalid file path.")

    if file_path.suffix.lower() != ".mp3":
        raise HTTPException(status_code=403, detail="Access denied.")

    display_name = sanitise_filename(name) if name else safe_filename
    if not display_name.lower().endswith(".mp3"):
        display_name += ".mp3"

    return FileResponse(
        str(file_path),
        media_type="audio/mpeg",
        filename=display_name,
    )

@app.post("/api/download")
@limiter.limit("10/minute")
async def download(request: Request, body: DownloadRequest, background_tasks: BackgroundTasks):
    """
    Download audio from YouTube and convert to MP3.
    Directly writes to target file stem to prevent bitrate collision.
    Uses reference-counted async locking per file.
    """
    url       = body.url.strip()
    title     = sanitise_filename(body.title or "audio")
    quality   = body.quality or "192"
    client_id = body.client_id

    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")

    target_stem    = f"{title}_{quality}k"
    cache_filename = f"{target_stem}.mp3"
    clean_filename = f"{title}.mp3"
    output_path    = DOWNLOADS_DIR / cache_filename

    # Serve immediately if already on disk
    if output_path.exists():
        logger.info("Cache hit - serving existing file: %s", cache_filename)
        encoded_cache = urllib.parse.quote(cache_filename)
        encoded_clean = urllib.parse.quote(clean_filename)
        return JSONResponse(content={
            "success":      True,
            "filename":     cache_filename,
            "download_url": f"/api/file/{encoded_cache}?name={encoded_clean}",
        })

    # Acquire lock for this specific file+quality
    async with _download_lock_registry.acquire(cache_filename):
        # Re-check after waiting for lock
        if output_path.exists():
            logger.info("Cache hit (post-lock) – serving: %s", cache_filename)
            encoded_cache = urllib.parse.quote(cache_filename)
            encoded_clean = urllib.parse.quote(clean_filename)
            return JSONResponse(content={
                "success":      True,
                "filename":     cache_filename,
                "download_url": f"/api/file/{encoded_cache}?name={encoded_clean}",
            })

        def progress_hook(d):
            if not client_id:
                return
            if d.get("status") == "downloading":
                percent_str = d.get("_percent_str", "0%")
                percent_str = re.sub(r"\x1b[^m]*m", "", percent_str).strip()
                _progress_data[client_id] = {"status": "downloading", "percent": percent_str}
            elif d.get("status") == "finished":
                _progress_data[client_id] = {"status": "converting", "percent": "100%"}

        ydl_opts = {
            **_get_base_ytdl_opts(),
            "format": "bestaudio/best",
            # Write directly to target stem so different qualities never collide
            "outtmpl": str(DOWNLOADS_DIR / f"{target_stem}.%(ext)s"),
            "prefer_ffmpeg": True,
            "progress_hooks": [progress_hook] if client_id else [],
            "writethumbnail": True,
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

            if not output_path.exists():
                raise HTTPException(
                    status_code=500,
                    detail="Download completed but output file not found on disk.",
                )

            logger.info("Download successful: %s", cache_filename)
            encoded_cache = urllib.parse.quote(cache_filename)
            encoded_clean = urllib.parse.quote(clean_filename)
            return JSONResponse(content={
                "success":      True,
                "filename":     cache_filename,
                "download_url": f"/api/file/{encoded_cache}?name={encoded_clean}",
            })

        except yt_dlp.utils.DownloadError as exc:
            logger.error("yt-dlp DownloadError: %s", exc)
            _cleanup_temp_files(target_stem)
            raise HTTPException(status_code=502, detail=f"Download failed: {str(exc)}")
        except HTTPException:
            _cleanup_temp_files(target_stem)
            raise
        except Exception as exc:
            logger.exception("Unexpected error during download")
            _cleanup_temp_files(target_stem)
            raise HTTPException(status_code=500, detail=str(exc))
        finally:
            if client_id:
                asyncio.create_task(_delayed_progress_cleanup(client_id))

# ── Entry point (local dev) ──────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
