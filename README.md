# 🎵 Melodyxx – YouTube MP3 Downloader (v2.2.4)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-enabled-2496ED.svg)](https://www.docker.com/)

A high-performance web application to search for songs on YouTube or explore complete artist discographies, preview audio directly in the browser, and download high-quality MP3 (128 / 192 / 320 kbps) with **official high-resolution album cover art & clean ID3 metadata**.

Powered by a **Cobalt-Style Zero-Disk Real-Time Streaming Pipeline** (**FastAPI** + **yt-dlp** + **FFmpeg Stream Pipes** + **Apple Music / iTunes Metadata Resolver**).

> ⚡ **Zero-Disk Footprint**: No audio files or artwork are ever written to the server's hard drive! Audio is streamed directly from YouTube CDN through FFmpeg in-memory pipes into the user's browser in real-time.
>
> 🎨 **Official Album Art & Clean Tags**: Automatically queries Apple Music for official high-resolution 800x800 square cover art and embeds APIC/TIT2/TPE1/TALB ID3v2 tags directly into the MP3 stream on the fly.
>
> 💿 **Artist Discography Mode & Batch Download**: Search any artist to browse up to 200 top popular songs and entire album/EP discographies, with sequential batch downloading.
>
> ✅ **Self-contained** – FFmpeg is bundled inside the project for Windows. Just clone/copy the folder and run `start.bat`.

---

## 🚀 Key Features

### 1. ⚡ Zero Disk I/O (Cobalt-Style Architecture)
* **0 bytes written to server storage**: Direct stream piping between YouTube CDN, FFmpeg, and the client browser (`pipe:1`).
* **Zero disk bottlenecks & SSD wear**: No temporary files to clean up, no risk of full-disk server crashes.
* **Minimal memory footprint**: Stream buffer is capped to ~64 KB per active download.
* **Instant Start (< 1s Latency)**: Download starts saving to the browser in 0.5 – 1.0 second. No 30-second waiting periods.

### 2. 🎨 High-Res Cover Art & Clean Metadata Embedding
* **Official Apple Music Artwork**: Automatically resolves clean track title and artist name to fetch official 800x800 album art.
* **Intelligent Title Sanitizer**: Strips YouTube noise like `[Official Music Video]`, `(MV)`, `4K 60FPS`, `SMTOWN`, `Lyric Video`, etc.
* **ID3v2 In-Stream Syncsafe Patching**: Dynamically injects `TIT2` (Title), `TPE1` (Artist), `TALB` (Album), `TYER` (Year), and `APIC` (Album Art) with valid syncsafe integer frame sizing. Compatible with Windows Media Player, Apple Music, car stereos, and third-party players.

### 3. 💿 Artist Discography Mode & Smart Deduplication
* **Dual Search Modes**: Toggle between single song search (`Lagu`) and artist discography (`Artis (Diskografi)`).
* **Up to 200 Top Songs**: Fetch and display up to 200 of the artist's most popular songs.
* **Configurable Display Limit**: Easily toggle between `25`, `50`, `100` (default), or `Semua lagu` (All tracks).
* **Smart Track Deduplication**: Merges duplicate tracks (e.g., single releases vs. full studio albums) and favors the studio album version while preserving genuine variations like *(Remix)*, *(Instrumental)*, *(Acoustic)*, or *(Japanese Version)*.
* **Albums & EPs Accordion**: Browse all studio albums and EPs with track counts and release years, with lazy-loaded tracklists on expansion.

### 4. 📦 Sequential Batch Downloader
* Multi-select any combination of popular songs and full albums with one click.
* **Non-blocking Sequential Engine**: Downloads tracks one-by-one with live progress indicators (track title, count, percentage bar) and a cancel button.
* Avoids browser popup blockers and prevents server connection flooding.

### 5. 🎛️ Global Audio Quality & Mini Player
* **Quality Selector**: Quick switch between `128k` (Data Saver), `192k` (Standard - Default), and `320k` (Ultra High Quality) with `localStorage` memory.
* **Persistent Mini Player**: Preview audio directly in-browser with interactive seekbar, volume control, time display, and synced play/pause buttons across all track rows.

### 6. 🌐 Download Manager & Browser Compatibility
* **Full HEAD Request Support**: Compatible with Free Download Manager (FDM), Internet Download Manager (IDM), `curl`, and `aria2`.
* **Token & Query Fallback**: Prevents HTTP 400 errors during two-pass download handshakes.

---

## 📁 Project Structure

```
melodyxx/
├── main.py                 # FastAPI backend & Zero-disk stream piping engine
├── metadata_resolver.py    # Apple Music & YouTube metadata and artwork resolver
├── requirements.txt        # Python dependencies
├── start.bat               # ⚡ Windows launcher (auto-setup & launch)
├── start.sh                # ⚡ Linux / macOS launcher
├── Dockerfile              # Docker image (FFmpeg + Python 3.11)
├── docker-compose.yml      # Docker Compose configuration
├── ffmpeg/
│   └── bin/
│       ├── ffmpeg.exe      # Bundled FFmpeg binary (Windows)
│       └── ffprobe.exe     # Bundled FFprobe binary (Windows)
└── static/
    ├── index.html          # Semantic HTML5 layout
    ├── css/
    │   └── style.css       # Design tokens, discography cards & dark theme styles
    ├── js/
    │   └── app.js          # Client controller, batch queue, audio player & discography UI
    ├── logo.png            # App logo
    ├── manifest.json       # PWA manifest
    └── sw.js               # Service Worker for offline app-shell caching (v14)
```

---

## 🚀 Getting Started

### ✅ Option 1 – Windows (Easiest) ⭐

Make sure **Python 3.11+** is installed, then simply:

```
Double-click → start.bat
```

The launcher will automatically:
- Create a virtual environment (`venv/`) if not present
- Install all dependencies from `requirements.txt`
- Detect the bundled FFmpeg in `ffmpeg/bin/`
- Open the application at **http://localhost:8000**

---

### ✅ Option 2 – Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

> **Note for Linux / macOS:** Install FFmpeg via your system package manager:
> ```bash
> # Debian / Ubuntu
> sudo apt update && sudo apt install ffmpeg
>
> # macOS (Homebrew)
> brew install ffmpeg
> ```

---

### ✅ Option 3 – Docker / Portainer

```bash
docker compose up -d --build
```

For Portainer:
1. Create a new stack pointing to this repository (`https://github.com/iFelzz/listen-now.git`).
2. Deploy stack.
3. For updates, use **Pull and redeploy** with clean build cache.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web application interface |
| `GET` | `/api/health` | Service health status & active stream count |
| `GET` | `/api/storage` | Zero-disk statistics & active stream counters |
| `GET` | `/api/git-commit` | Current git commit hash for deployment badge |
| `GET` | `/api/search?q=&limit=` | Fast YouTube search (default 10, max 50) |
| `GET` | `/api/artist/search?q=&limit=` | Search artists on Apple Music catalog (default 8) |
| `GET` | `/api/artist/{id}/discography` | Fetch top popular songs (up to 200) and album list |
| `GET` | `/api/album/{id}/tracks` | Fetch full tracklist of a specific album/EP |
| `GET` | `/api/preview?url=` | Extract audio stream URL for in-browser preview |
| `POST` | `/api/download` | Pre-resolve stream in ~0.5s, fetch cover art & issue token |
| `GET` | `/api/stream?token=&quality=` | Token-authorized on-the-fly MP3 audio streaming pipe (`pipe:1`) |

---

## 🌐 Advanced Configuration (Proxy, Cookies & Security)

To bypass YouTube bot checks or datacenter IP restrictions on cloud VPS:
* **Cookies**: Place a `cookies.txt` file in the project root directory, or set the environment variable:
  ```env
  YTDLP_COOKIES_FILE=/path/to/cookies.txt
  ```
* **Proxy**: Set the HTTP/SOCKS5 proxy environment variable:
  ```env
  YTDLP_PROXY=http://user:pass@host:port
  ```
* **Custom Allowed CORS Origins**: By default `listennow.ifelz.my.id` and `localhost` are allowed. To add custom domains:
  ```env
  ALLOWED_ORIGINS=https://listennow.ifelz.my.id,https://yourdomain.com
  ```

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11+, FastAPI, Uvicorn, SlowAPI |
| **Streaming Pipeline** | yt-dlp + FFmpeg In-Memory Pipes (`pipe:1`) |
| **Metadata & Artwork** | Apple Music / iTunes API + In-Stream ID3v2 APIC Patcher |
| **Frontend** | HTML5, CSS3 Tokens, Vanilla ES6+ JS, PWA Service Worker |
| **Container** | Docker (Debian Bookworm-slim), Docker Compose |

---

## 📄 License & Attribution

This project is licensed under the **GNU Affero General Public License v3.0 (GNU AGPLv3)** — see the [LICENSE](LICENSE) file for details.

### 🙏 Acknowledgements & Inspirations

Melodyxx was built with inspiration and tools from the open-source community:
* **[Cobalt](https://github.com/imputnet/cobalt)** by [wukko / imputnet](https://github.com/imputnet) — for pioneering the zero-disk real-time streaming philosophy.
* **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — for rock-solid media extraction.
* **[FFmpeg](https://ffmpeg.org)** — for in-memory stream processing and transcoding.
* **[FastAPI](https://fastapi.tiangolo.com)** — for the high-performance asynchronous web framework.

Melodyxx &copy; 2026 &mdash; Created by [iFelzz](https://github.com/iFelzz).
