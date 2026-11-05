<div align="center">
  <img src="static/logo.png" alt="Melodyxx Logo" width="120" />
  <h1>Melodyxx</h1>
  <p><strong>Zero-Disk YouTube MP3 Downloader & Discography Browser</strong></p>

  <p>
    <a href="https://www.gnu.org/licenses/agpl-3.0"><img src="https://img.shields.io/badge/License-AGPL_v3-7c3aed.svg" alt="License: AGPL v3" /></a>
    <a href="https://github.com/iFelzz/listen-now/releases"><img src="https://img.shields.io/badge/Version-1.6.1-a855f7.svg" alt="Version: 1.6.1" /></a>
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11+-3776ab.svg" alt="Python: 3.11+" /></a>
    <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.111.0-009688.svg" alt="FastAPI" /></a>
    <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-enabled-2496ED.svg" alt="Docker" /></a>
  </p>
</div>

---

## Overview

Melodyxx is a high-performance audio extraction web application designed for fast, seamless music discovery and downloads. Built on a cobalt-style zero-disk streaming architecture, it pipes audio on the fly directly from YouTube CDNs through FFmpeg into client downloads with zero temporary files written to server storage.

Melodyxx automatically resolves and embeds official 800x800 album art from Apple Music, synchronizes ID3v2 metadata frames, and provides a full artist discography browser with sequential batch downloading capabilities.

---

## Features

### Zero-Disk Streaming Pipeline
* **Zero disk usage**: Audio data is transcoded and streamed directly via in-memory pipes (`stdout -> client response`). The server disk footprint remains strictly 0 MB.
* **Instant response**: Downloads begin streaming to the client browser in under one second without server-side pre-rendering delays.
* **Resource safe**: Active FFmpeg processes are bounded by an internal concurrency semaphore to protect system memory and CPU throughput.

### High-Resolution Artwork & ID3 Metadata
* **Official Apple Music resolution**: Queries Apple Music and iTunes catalog APIs to fetch official 800x800 square cover art.
* **In-stream ID3v2 frame sync**: Dynamically calculates and injects standard `TIT2` (Title), `TPE1` (Artist), `TALB` (Album), `TYER` (Year), and `APIC` (Cover Art) frames on the fly.
* **Automatic title cleaning**: Sanitizes YouTube noise tags like `[Official Video]`, `(MV)`, `4K 60FPS`, `Lyric Video`, and release channels.
* **Auto-fallback streaming**: Automatically falls back to clean audio streams if cover art CDNs experience latency, preventing stalled or 0 KB files.

### Artist Discography Browser
* **Dual search mode**: Switch seamlessly between individual track search and Apple Music artist discography catalog.
* **Top tracks & full discography**: Browse popular tracks (up to 200 songs) and studio albums/EPs with complete tracklists.
* **Smart deduplication**: Consolidates track listings to favor official studio album releases while preserving remixes, acoustic versions, and language variants.

### Sequential Batch Downloader
* Multi-select individual songs or full album tracklists.
* Controlled sequential queue downloads each track in order, avoiding browser download pop-up blocking and server connection flooding.
* Interactive progress drawer with live status, percentage, count, and retry options.

### Audio Preview Player & Quality Selector
* **Persistent in-browser preview**: Built-in glassmorphism mini player with live seekbar, volume control, and track-row synchronization.
* **Quality selection**: Choose between 128 kbps (Data Saver), 192 kbps (Standard), 320 kbps (High Quality), or native M4A.

### Security & Hotlink Protection
* **Token-gated streaming**: Direct access to `/api/stream` requires a cryptographically secure token issued by `/api/download` with a 15-minute time-to-live window.
* **Origin & referer validation**: Protects against 3rd-party hotlinking and unauthorized iframe embedding.
* **Reverse-proxy real IP detection**: Accurate rate-limiting per real user when deployed behind Cloudflare, Nginx, or Docker reverse proxies.

---

## Architecture

```
[ YouTube Audio CDN ] ─── (HTTP Stream) ───┐
                                            ├─► [ FFmpeg Process (pipe:1) ] ──► [ Client Response ]
[ Apple Music Artwork ] ── (JPEG Buffer) ──┘        │
                                                    ▼
                                            [ ID3v2 Syncsafe Frame Patcher ]
```

---

## Project Structure

```
melodyxx/
├── main.py                 # FastAPI application, streaming engine & security handlers
├── metadata_resolver.py    # Apple Music & YouTube metadata and artwork resolver
├── requirements.txt        # Python backend dependencies
├── start.bat               # Windows quick-launch script
├── start.sh                # Linux / macOS launcher script
├── Dockerfile              # Container definition (Python 3.11 + FFmpeg)
├── docker-compose.yml      # Container orchestration
├── ffmpeg/
│   └── bin/
│       ├── ffmpeg.exe      # Bundled FFmpeg binary (Windows)
│       └── ffprobe.exe     # Bundled FFprobe binary (Windows)
└── static/
    ├── index.html          # Application markup & UI layout
    ├── css/
    │   └── style.css       # Violet neon glassmorphism stylesheet
    ├── js/
    │   └── app.js          # Client application logic, batch queue & audio player
    ├── logo.png            # Application branding icon
    ├── manifest.json       # PWA manifest
    └── sw.js               # Service Worker for client-side caching
```

---

## Getting Started

### Windows

Make sure **Python 3.11+** is installed on your system:

```cmd
start.bat
```

The script will automatically set up the virtual environment, install requirements, link the bundled FFmpeg, and start the application on `http://localhost:8000`.

---

### Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

> **Prerequisite**: Install FFmpeg using your system package manager:
> ```bash
> # Debian / Ubuntu
> sudo apt update && sudo apt install ffmpeg
>
> # macOS (Homebrew)
> brew install ffmpeg
> ```

---

### Docker & Portainer

```bash
docker compose up -d --build
```

For Portainer deployments:
1. Create a new stack pointing to repository `https://github.com/iFelzz/listen-now.git`.
2. Deploy the stack.
3. For updates, trigger **Pull and redeploy**.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web application user interface |
| `GET` | `/api/version` | Current semantic version and git commit metadata |
| `GET` | `/api/health` | System status, active stream count, and zero-disk verification |
| `GET` | `/api/storage` | Active memory cache metrics and streaming statistics |
| `GET` | `/api/search?q=&limit=` | YouTube audio search with metadata extraction |
| `GET` | `/api/artist/search?q=&limit=` | Apple Music artist catalog search |
| `GET` | `/api/artist/{id}/discography` | Artist discography, popular songs, and album catalog |
| `GET` | `/api/album/{id}/tracks` | Tracklist extraction for a specific album or EP |
| `GET` | `/api/preview?url=` | Audio preview stream extraction for in-browser playback |
| `POST` | `/api/download` | Pre-resolve stream, fetch official artwork, and issue download token |
| `GET` | `/api/stream?token=&quality=` | Token-authorized on-the-fly MP3 audio streaming pipe |
| `GET` | `/stats` | Internal analytics & metrics dashboard |
| `GET` | `/api/stats` | Streaming, bandwidth & concurrency metrics (JSON) |
| `POST` | `/api/stats/reset` | Reset analytics counters (Admin key required) |

---

## Configuration

Environment variables can be configured in a `.env` file or passed through the container environment:

| Variable | Description | Default |
|---|---|---|
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS domains | `https://listennow.ifelz.my.id,localhost` |
| `ADMIN_KEY` | Admin authorization key for analytics resets and stats | `melodyxx-admin` |
| `YTDLP_PROXY` | HTTP or SOCKS5 proxy URL for YouTube extraction requests | `None` |
| `YTDLP_COOKIES_FILE` | Path to `cookies.txt` for YouTube authentication bypass | `None` |

---

## Tech Stack

* **Backend**: Python 3.11+, FastAPI, Uvicorn, SlowAPI
* **Streaming Engine**: yt-dlp, FFmpeg In-Memory Pipes (`pipe:1`)
* **Metadata & Art**: Apple Music API, iTunes Store API, ID3v2 Syncsafe In-Stream Patcher
* **Frontend**: Vanilla HTML5, Modern CSS3 Custom Properties, ES6+ JavaScript, PWA Service Worker
* **Deployment**: Docker, Docker Compose, Debian Bookworm-slim

---

## License & Attribution

This project is licensed under the **GNU Affero General Public License v3.0 (GNU AGPLv3)**. See the [LICENSE](LICENSE) file for complete terms.

### Acknowledgements

Melodyxx is built with inspiration and tools from the open-source community:
* [Cobalt](https://github.com/imputnet/cobalt) by [imputnet](https://github.com/imputnet) — for pioneering the zero-disk real-time streaming philosophy.
* [yt-dlp](https://github.com/yt-dlp/yt-dlp) — media extraction backend.
* [FFmpeg](https://ffmpeg.org) — audio transcoding and pipe processing.
* [FastAPI](https://fastapi.tiangolo.com) — asynchronous web framework.

---

Melodyxx © 2026 • Built by [iFelzz](https://github.com/iFelzz)
