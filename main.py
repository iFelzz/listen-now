"""
Listen Now – Zero-Disk Streaming Backend (Cobalt-Style Pipeline)
───────────────────────────────────────────────────────────────
Architecture:
  - Zero-Disk Storage: 0 bytes written to disk. All media is processed in-memory.
  - On-The-Fly Stream Piping: YouTube CDN → FFmpeg stream pipe → FastAPI StreamingResponse → Browser.
  - Rich Music Metadata & Studio Artwork: Auto-fetches official 800x800 square cover art (iTunes/YouTube)
    and embeds ID3v2 APIC cover art + title + artist + album + year into the MP3 stream on the fly.
  - Ultra-Low Resource Usage: Tiny RAM buffer (~64 KB chunks), no disk I/O thrashing.
  - Instant Response: Browser download starts within ~0.5 - 1.0 second.
  - Safe Process Lifecycle: FFmpeg subprocesses terminate cleanly on client disconnect.
  - Download Manager Compatible: Supports HEAD pre-checks and multi-connection managers (FDM, IDM).

Endpoints:
  GET  /                     → Frontend UI (index.html)
  GET  /favicon.ico          → App favicon
  GET  /api/health           → Health & architecture status
  GET  /api/version          → Git commit hash & version
  GET  /api/search           → Fast YouTube search (rate-limited: 30/min per IP)
  GET  /api/preview          → Direct audio stream preview (rate-limited: 20/min per IP)
  POST /api/download         → Pre-validate, resolve rich metadata & issue resilient stream token
  GET/HEAD /api/stream       → Stream on-the-fly MP3 directly to browser (Zero-disk)
  GET  /api/storage          → System status & active stream statistics
"""

import os
import re
import time
import secrets
import asyncio
import logging
import urllib.parse
import shutil
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

import yt_dlp
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import metadata_resolver

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# ── Environment & External Config ────────────────────────────
CLEANUP_TOKEN = os.environ.get("CLEANUP_TOKEN")
YTDLP_PROXY   = os.environ.get("YTDLP_PROXY")

COOKIES_FILE = os.environ.get("YTDLP_COOKIES_FILE")
if not COOKIES_FILE and (BASE_DIR / "cookies.txt").exists():
    COOKIES_FILE = str(BASE_DIR / "cookies.txt")

if COOKIES_FILE:
    logger.info("Using yt-dlp cookies from: %s", COOKIES_FILE)
if YTDLP_PROXY:
    logger.info("Using yt-dlp proxy: %s", YTDLP_PROXY)

# ── FFmpeg Detection ─────────────────────────────────────────
def get_ffmpeg_binary() -> str:
    """Detect and return path to ffmpeg executable."""
    bundled_exe = BASE_DIR / "ffmpeg" / "bin" / "ffmpeg.exe"
    if bundled_exe.exists():
        return str(bundled_exe)
    bundled_bin = BASE_DIR / "ffmpeg" / "bin" / "ffmpeg"
    if bundled_bin.exists():
        return str(bundled_bin)
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    winget = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"
    if winget.exists():
        return str(winget)
    return "ffmpeg"

FFMPEG_BIN = get_ffmpeg_binary()
logger.info("FFmpeg binary selected: %s", FFMPEG_BIN)

FFMPEG_LOCATION = str(Path(FFMPEG_BIN).parent) if Path(FFMPEG_BIN).is_file() else None

# ── Git Commit Detection ─────────────────────────────────────
# Embedded fallback hash matching the current release commit
BUILTIN_COMMIT = "aca0fdc"

def get_commit_hash() -> str:
    """Detect current Git commit hash from env, git CLI, .git/HEAD, version.json, or builtin."""
    # 1. Environment variable (e.g. from Docker/Portainer build args)
    env_hash = os.environ.get("COMMIT_HASH") or os.environ.get("GIT_COMMIT")
    if env_hash and env_hash.strip() not in ("latest", "unknown", ""):
        return env_hash.strip()[:7]

    # 2. Direct git CLI execution if git binary is present
    if shutil.which("git"):
        try:
            import subprocess
            out = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(BASE_DIR),
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            if out and out.strip():
                return out.strip()[:7]
        except Exception:
            pass

    # 3. Pure Python inspection of .git directory
    git_dir = BASE_DIR / ".git"
    if git_dir.exists():
        try:
            head_file = git_dir / "HEAD"
            if head_file.exists():
                ref = head_file.read_text(encoding="utf-8").strip()
                if ref.startswith("ref:"):
                    rel_ref = ref.split(" ", 1)[1].strip()
                    ref_path = git_dir / rel_ref
                    if ref_path.exists():
                        return ref_path.read_text(encoding="utf-8").strip()[:7]
                    packed = git_dir / "packed-refs"
                    if packed.exists():
                        for line in packed.read_text(encoding="utf-8").splitlines():
                            if line and not line.startswith(("#", "^")):
                                parts = line.split()
                                if len(parts) == 2 and parts[1] == rel_ref:
                                    return parts[0][:7]
                else:
                    return ref[:7]
        except Exception:
            pass

    # 4. Fallback to version.json file generated during build / deployment
    vfile = BASE_DIR / "version.json"
    if vfile.exists():
        try:
            vdata = json.loads(vfile.read_text(encoding="utf-8"))
            commit = vdata.get("commit")
            if commit and commit not in ("latest", "unknown", ""):
                return commit.strip()[:7]
        except Exception:
            pass

    return BUILTIN_COMMIT

COMMIT_HASH = get_commit_hash()
if COMMIT_HASH in ("latest", "unknown", ""):
    COMMIT_HASH = BUILTIN_COMMIT
logger.info("Current Git commit hash: %s", COMMIT_HASH)

def _get_base_ytdl_opts() -> dict[str, Any]:
    """Common base options for yt-dlp metadata extraction."""
    opts: dict[str, Any] = {
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
    if FFMPEG_LOCATION:
        opts["ffmpeg_location"] = FFMPEG_LOCATION
    if COOKIES_FILE:
        opts["cookiefile"] = COOKIES_FILE
    if YTDLP_PROXY:
        opts["proxy"] = YTDLP_PROXY
    return opts

# ── In-Memory Caches & Active Streams Tracker ─────────────────
_preview_cache: dict[str, dict] = {}
_PREVIEW_TTL_SECONDS = 600   # 10 minutes

_search_cache: dict[str, dict] = {}
_SEARCH_TTL_SECONDS = 300    # 5 minutes

_stream_tokens: dict[str, dict] = {}
_TOKEN_TTL_SECONDS = 900     # 15 minutes (allows download managers to reconnect & probe)

_MAX_CACHE_ENTRIES = 300
_active_streams_count: int = 0

def prune_memory_caches() -> None:
    """Evict expired entries and enforce memory cache boundaries."""
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

    # 3. Prune stream tokens
    expired_tokens = [k for k, v in _stream_tokens.items() if (now - v.get("created_at", 0)) > _TOKEN_TTL_SECONDS]
    for k in expired_tokens:
        _stream_tokens.pop(k, None)

async def _cache_maintenance_loop():
    """Periodic memory maintenance task."""
    while True:
        await asyncio.sleep(60)
        try:
            prune_memory_caches()
        except Exception as exc:
            logger.error("Cache maintenance error: %s", exc)

# ── Lifespan ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Listen Now (Zero-Disk Streaming Engine v2.1)...")
    try:
        ver = yt_dlp.version.__version__
        logger.info("yt-dlp version: %s", ver)
    except Exception:
        pass

    maintenance_task = asyncio.create_task(_cache_maintenance_loop())
    yield
    maintenance_task.cancel()

# ── Rate Limiter ──────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["400/day"])

# ── FastAPI App ───────────────────────────────────────────────
app = FastAPI(
    title="Listen Now",
    description="YouTube MP3 Downloader powered by Zero-Disk Stream Piping (Cobalt-Style) & Auto-Cover Art",
    version="2.1.0",
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

# Serve static assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Pydantic Models ───────────────────────────────────────────
ALLOWED_QUALITIES = {"128", "192", "320", "native", "m4a"}

class DownloadRequest(BaseModel):
    url:       str
    title:     Optional[str] = "audio"
    quality:   Optional[str] = "192"

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: str) -> str:
        if v not in ALLOWED_QUALITIES:
            raise ValueError(f"quality must be one of {sorted(ALLOWED_QUALITIES)}")
        return v

# ── Helpers ───────────────────────────────────────────────────
def sanitise_filename(name: str) -> str:
    """Clean filename of illegal characters across Windows and Linux."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:150] if name else "audio"

def _extract_stream_info(url: str, raw_title: str = "") -> dict:
    """
    Extract direct audio stream URL and video metadata synchronously via yt-dlp,
    then automatically resolve clean song tags and high-res cover art.
    """
    ydl_opts = {
        **_get_base_ytdl_opts(),
        "format": "bestaudio/best",
        "extract_flat": False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            raise ValueError("No video information found.")
        if "entries" in info and info["entries"]:
            info = info["entries"][0]

        stream_url = info.get("url")
        if not stream_url:
            raise ValueError("Direct audio stream URL could not be resolved.")

        headers = info.get("http_headers") or {}
        yt_raw_title = raw_title or info.get("title") or "audio"

        # Resolve rich official metadata (cover art, clean title, artist, album, year)
        rich_meta = metadata_resolver.resolve_rich_metadata(info, yt_raw_title)

        return {
            "stream_url": stream_url,
            "title":      rich_meta.get("title") or info.get("title") or "audio",
            "artist":     rich_meta.get("artist") or info.get("uploader") or "Unknown Artist",
            "album":      rich_meta.get("album") or "",
            "year":       rich_meta.get("year") or "",
            "poster_url": rich_meta.get("poster_url") or "",
            "duration":   info.get("duration") or 0,
            "user_agent": headers.get("User-Agent"),
        }

# ── Routes ────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    """Serve the frontend single page app."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found.")
    return FileResponse(str(index_path))

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon."""
    favicon_path = STATIC_DIR / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(str(favicon_path))
    logo_path = STATIC_DIR / "logo.png"
    if logo_path.exists():
        return FileResponse(str(logo_path), media_type="image/png")
    raise HTTPException(status_code=404, detail="Favicon not found.")

@app.get("/api/version")
async def get_version():
    """Return Git commit hash and app version."""
    global COMMIT_HASH
    if not COMMIT_HASH or COMMIT_HASH in ("latest", "unknown"):
        COMMIT_HASH = get_commit_hash()

    return {
        "commit": COMMIT_HASH,
        "version": "2.1.2",
        "commit_url": f"https://github.com/iFelzz/listen-now/commit/{COMMIT_HASH}"
    }

@app.get("/api/health")
async def health():
    """Health & architecture check endpoint."""
    return {
        "status": "ok",
        "service": "Listen Now",
        "architecture": "zero-disk-stream-piping",
        "active_streams": _active_streams_count,
        "commit": COMMIT_HASH,
        "disk_usage_bytes": 0,
        "version": "2.1.2",
    }

@app.get("/api/storage")
async def storage_info():
    """System information & stream statistics (0 disk usage guaranteed)."""
    return JSONResponse(content={
        "mode": "Zero-Disk Streaming (Cobalt-Style Pipeline)",
        "disk_usage_mb": 0.0,
        "active_streams": _active_streams_count,
        "cached_searches": len(_search_cache),
        "cached_previews": len(_preview_cache),
        "active_tokens": len(_stream_tokens),
    })

@app.get("/api/search")
@limiter.limit("30/minute")
async def search(request: Request, q: str, limit: int = 10):
    """
    Search YouTube and return video results with metadata.
    Rate-limited: 30 req/min.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required.")

    limit = min(max(1, limit), 50)
    q_stripped = q.strip()
    is_url = q_stripped.startswith("http://") or q_stripped.startswith("https://")
    search_query = q_stripped if is_url else f"ytsearch{limit}:{q_stripped}"

    cache_key = f"{q_stripped.lower()}::{limit}"
    if not is_url:
        cached = _search_cache.get(cache_key)
        if cached and (time.time() - cached["ts"]) < _SEARCH_TTL_SECONDS:
            return JSONResponse(content={"results": cached["results"]})

    ydl_opts = {
        **_get_base_ytdl_opts(),
        "extract_flat": True,
        "skip_download": True,
    }

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

        if not is_url:
            if len(_search_cache) >= _MAX_CACHE_ENTRIES:
                prune_memory_caches()
            _search_cache[cache_key] = {"results": results, "ts": time.time()}

        return JSONResponse(content={"results": results})

    except yt_dlp.utils.DownloadError as exc:
        logger.error("yt-dlp Search Error: %s", exc)
        raise HTTPException(status_code=502, detail=f"YouTube search failed: {str(exc)}")
    except Exception as exc:
        logger.exception("Unexpected error during search")
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/preview")
@limiter.limit("20/minute")
async def preview(request: Request, url: str):
    """
    Extract best direct audio stream URL for in-browser audio playback.
    Cached for up to 10 minutes.
    """
    if not url.strip():
        raise HTTPException(status_code=400, detail="URL is required")

    cached = _preview_cache.get(url)
    if cached and (time.time() - cached["ts"]) < _PREVIEW_TTL_SECONDS:
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

        return {"stream_url": stream_url}
    except Exception as exc:
        logger.error("Preview error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to extract preview: {str(exc)}")

@app.post("/api/download")
@limiter.limit("30/minute")
async def prepare_download(request: Request, body: DownloadRequest):
    """
    Resolve YouTube audio stream in ~0.5s, auto-fetch official poster artwork & clean metadata,
    and return resilient direct streaming download link.
    """
    url     = body.url.strip()
    quality = body.quality or "192"

    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")

    try:
        info = await asyncio.to_thread(_extract_stream_info, url, body.title or "")
    except Exception as exc:
        logger.error("Stream extraction failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Failed to resolve audio: {str(exc)}")

    clean_title  = sanitise_filename(info["title"])
    clean_artist = sanitise_filename(info["artist"])
    clean_album  = sanitise_filename(info.get("album", ""))
    year         = info.get("year", "")
    poster_url   = info.get("poster_url", "")
    token        = secrets.token_urlsafe(16)

    _stream_tokens[token] = {
        "stream_url": info["stream_url"],
        "title":      clean_title,
        "artist":     clean_artist,
        "album":      clean_album,
        "year":       year,
        "poster_url": poster_url,
        "quality":    quality,
        "user_agent": info["user_agent"],
        "created_at": time.time(),
    }

    ext = "m4a" if quality in ("native", "m4a") else "mp3"
    filename = f"{clean_title}.{ext}"

    # Embed token AND fallback query params so the URL never 400s under multiple connections or retries
    encoded_url    = urllib.parse.quote(url)
    encoded_title  = urllib.parse.quote(clean_title)
    encoded_artist = urllib.parse.quote(clean_artist)
    encoded_album  = urllib.parse.quote(clean_album)
    encoded_year   = urllib.parse.quote(year)
    encoded_poster = urllib.parse.quote(poster_url)

    download_url = (
        f"/api/stream?token={token}&url={encoded_url}&quality={quality}"
        f"&title={encoded_title}&artist={encoded_artist}&album={encoded_album}&year={encoded_year}&poster={encoded_poster}"
    )

    logger.info("Stream token created: %s (%s by %s, %s kbps)", token, clean_title, clean_artist, quality)

    return JSONResponse(content={
        "success":      True,
        "filename":     filename,
        "title":        clean_title,
        "artist":       clean_artist,
        "album":        clean_album,
        "poster_url":   poster_url,
        "download_url": download_url,
    })

def fix_id3_size_in_stream(buffer: bytearray) -> int:
    """
    FFmpeg cannot seek back to update the ID3v2 tag size when writing to pipe:1 (stdout).
    This function parses the consecutive ID3v2.3 frames (TIT2, TPE1, APIC, etc.),
    calculates the total ID3v2 payload size, and patches bytes 6-9 with the proper syncsafe integer.
    Returns the total tag size (including 10-byte header) if successfully parsed, or 0 if more data is needed.
    """
    if len(buffer) < 10 or buffer[:3] != b"ID3":
        return 0

    offset = 10
    total_len = len(buffer)

    while True:
        if offset + 10 > total_len:
            # Need more data from pipe to read the next frame header
            return 0

        frame_id = bytes(buffer[offset:offset+4])
        # If frame_id is padding (zeros) or MPEG audio sync word (0xFF 0xFB...), we reached the end of ID3 frames
        if frame_id == b"\x00\x00\x00\x00" or (buffer[offset] == 0xFF and (buffer[offset+1] & 0xE0) == 0xE0):
            break

        # Check if frame_id consists of 4 alphanumeric uppercase characters (e.g. TIT2, TPE1, APIC)
        if not (all(0x20 <= b <= 0x7E for b in frame_id) and frame_id.isalnum()):
            break

        frame_size = int.from_bytes(buffer[offset+4:offset+8], "big")
        if frame_size <= 0:
            break

        if offset + 10 + frame_size > total_len:
            # Full frame (e.g. large APIC image) is still arriving in upcoming chunks
            return 0

        offset += 10 + frame_size

    # The ID3v2 size field represents the total tag size EXCLUDING the 10-byte header
    id3_payload_size = offset - 10
    if id3_payload_size > 0:
        # Encode as 4-byte syncsafe integer (7 bits per byte)
        buffer[6] = (id3_payload_size >> 21) & 0x7F
        buffer[7] = (id3_payload_size >> 14) & 0x7F
        buffer[8] = (id3_payload_size >> 7)  & 0x7F
        buffer[9] = id3_payload_size & 0x7F
        return offset

    return 0

@app.api_route("/api/stream", methods=["GET", "HEAD"])
async def stream_audio(
    request: Request,
    token: Optional[str] = None,
    url: Optional[str] = None,
    quality: Optional[str] = "192",
    title: Optional[str] = None,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    year: Optional[str] = None,
    poster: Optional[str] = None,
):
    """
    On-The-Fly Real-Time Audio Streaming (Cobalt-Style Pipeline).
    Pipes YouTube CDN audio through FFmpeg stdout directly to HTTP client response.
    Embeds official album artwork (APIC attached pic) and ID3 tags on the fly.
    Zero disk writes. Zero storage footprint. Instant playback & download.
    """
    stream_url    = None
    stream_title  = "audio"
    stream_artist = "Listen Now"
    stream_album  = ""
    stream_year   = ""
    poster_url    = None
    stream_quality = quality or "192"
    user_agent    = None

    # Option 1: Retrieve from token without popping (token stays active for 15 mins for multi-connection managers)
    if token and token in _stream_tokens:
        token_data = _stream_tokens[token]
        if (time.time() - token_data.get("created_at", 0)) < _TOKEN_TTL_SECONDS:
            stream_url     = token_data["stream_url"]
            stream_title   = token_data["title"]
            stream_artist  = token_data["artist"]
            stream_album   = token_data.get("album", "")
            stream_year    = token_data.get("year", "")
            poster_url     = token_data.get("poster_url")
            stream_quality = token_data["quality"]
            user_agent     = token_data["user_agent"]

    # Option 2: Fallback to direct resolution if token expired or missing
    if not stream_url and url:
        try:
            info = await asyncio.to_thread(_extract_stream_info, url.strip(), title or "")
            stream_url     = info["stream_url"]
            stream_title   = sanitise_filename(title or info["title"])
            stream_artist  = artist or info["artist"]
            stream_album   = album or info.get("album", "")
            stream_year    = year or info.get("year", "")
            poster_url     = poster or info.get("poster_url")
            stream_quality = quality or "192"
            user_agent     = info["user_agent"]
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to resolve audio stream: {str(exc)}")

    if not stream_url:
        raise HTTPException(status_code=400, detail="Invalid, expired, or missing stream parameters.")

    is_native = stream_quality in ("native", "m4a")
    ext = "m4a" if is_native else "mp3"
    media_type = "audio/mp4" if is_native else "audio/mpeg"
    output_filename = f"{stream_title}.{ext}"

    quoted_filename = urllib.parse.quote(output_filename)
    ascii_filename  = re.sub(r'[^\x20-\x7E]', '', stream_title) or "audio"
    content_disp    = f'attachment; filename="{ascii_filename}.{ext}"; filename*=UTF-8\'\'{quoted_filename}'

    # Fast response for HEAD pre-checks from Download Managers (FDM, IDM)
    if request.method == "HEAD":
        return Response(
            status_code=200,
            media_type=media_type,
            headers={
                "Content-Disposition": content_disp,
                "Accept-Ranges":       "none",
                "Cache-Control":       "no-cache, no-store, must-revalidate",
            }
        )

    # Build FFmpeg command for in-memory stream piping
    has_poster = bool(poster_url and not is_native)

    cmd = [
        FFMPEG_BIN,
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
    ]
    if user_agent:
        cmd.extend(["-user_agent", user_agent])

    cmd.extend(["-i", stream_url])

    if has_poster:
        # Dual-input: Input 0 = audio stream, Input 1 = cover art poster image
        cmd.extend([
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", poster_url,
            "-map", "0:a",
            "-map", "1:v",
            "-c:a", "libmp3lame",
            "-b:a", f"{stream_quality}k",
            "-c:v", "mjpeg",
            "-disposition:v:0", "attached_pic",
        ])
    elif not is_native:
        cmd.extend([
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", f"{stream_quality}k",
        ])

    if is_native:
        # Native direct stream copy: 0% CPU usage
        cmd.extend([
            "-vn",
            "-c:a", "copy",
            "-movflags", "frag_keyframe+empty_moov+default_base_moof",
            "-f", "mp4",
            "pipe:1"
        ])
    else:
        # Standard ID3v2.3 tags with rich metadata
        cmd.extend([
            "-id3v2_version", "3",
            "-metadata", f"title={stream_title}",
            "-metadata", f"artist={stream_artist}",
        ])
        if stream_album:
            cmd.extend(["-metadata", f"album={stream_album}"])
        if stream_year:
            cmd.extend(["-metadata", f"date={stream_year}"])
        cmd.extend([
            "-f", "mp3",
            "pipe:1"
        ])

    logger.info("Spawning stream pipe: %s (%s) [has_poster=%s]", output_filename, stream_quality, has_poster)

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except Exception as exc:
        logger.error("Failed to spawn FFmpeg process: %s", exc)
        raise HTTPException(status_code=500, detail="Audio conversion pipeline failed to start.")

    async def chunk_generator():
        global _active_streams_count
        _active_streams_count += 1
        logger.info("Stream opened: %s (Active streams: %d)", output_filename, _active_streams_count)

        header_patched = False
        initial_buffer = bytearray()

        try:
            while True:
                chunk = await process.stdout.read(64 * 1024)  # 64 KB chunks
                if not chunk:
                    # Stream finished: flush any remaining initial buffer
                    if initial_buffer:
                        if not header_patched and not is_native:
                            fix_id3_size_in_stream(initial_buffer)
                        yield bytes(initial_buffer)
                    break

                if not header_patched and not is_native:
                    initial_buffer.extend(chunk)
                    patched = fix_id3_size_in_stream(initial_buffer)
                    # Once patched or safety threshold (512 KB) reached, flush header buffer
                    if patched > 0 or len(initial_buffer) >= 512 * 1024:
                        header_patched = True
                        yield bytes(initial_buffer)
                        initial_buffer.clear()
                else:
                    yield chunk
        except (asyncio.CancelledError, GeneratorExit):
            logger.info("Client disconnected early from stream: %s", output_filename)
        finally:
            _active_streams_count = max(0, _active_streams_count - 1)
            logger.info("Stream closed: %s (Remaining active: %d)", output_filename, _active_streams_count)
            if process.returncode is None:
                try:
                    process.terminate()
                    await process.wait()
                except Exception:
                    pass

    return StreamingResponse(
        chunk_generator(),
        media_type=media_type,
        headers={
            "Content-Disposition": content_disp,
            "Accept-Ranges":       "none",
            "Cache-Control":       "no-cache, no-store, must-revalidate",
            "Pragma":              "no-cache",
            "Expires":             "0",
        }
    )

# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
