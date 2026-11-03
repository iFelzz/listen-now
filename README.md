# 🎵 Listen Now – YouTube MP3 Downloader (v2.0)

A high-performance web application to search for songs on YouTube, preview audio directly in the browser, and download high-quality MP3 (128 / 192 / 320 kbps) or Native M4A audio. 

Powered by a **Cobalt-Style Zero-Disk Real-Time Streaming Pipeline** (**FastAPI** + **yt-dlp** + **FFmpeg Stream Pipes**).

> ⚡ **Zero-Disk Footprint**: No files are ever saved to the server's hard drive! Audio is streamed directly from YouTube CDN through FFmpeg in-memory pipes into the user's browser in real-time.
>
> ✅ **Self-contained** – FFmpeg is bundled inside the project for Windows. Just clone/copy the folder and run `start.bat`.

---

## 🚀 Key Features

* **Zero Disk I/O (Cobalt-Style Architecture)**:
  - 0 bytes written to server storage.
  - No disk bottlenecks, no SSD wear, no full-disk crashes.
  - Memory footprint is capped to a tiny ~64 KB stream buffer per download.
* **Instant Start (< 1s Latency)**:
  - Browser download starts immediately within 0.5 - 1.0 second. Users no longer wait 30 seconds for server-side downloading & encoding before the file starts saving.
* **Format & Quality Options**:
  - `MP3 192k` (Standard - Default)
  - `MP3 320k` (High-definition audio)
  - `MP3 128k` (Data saver)
  - `⚡ M4A` (Native AAC direct stream copy, **0% CPU usage**)
* **Metadata & Tagging On-The-Fly**:
  - Title and Artist ID3v2 tags are injected dynamically into the MP3 stream on the fly.
* **Modular Frontend & PWA**:
  - Clean separated HTML, CSS, and JS.
  - PWA offline caching via Service Worker.
  - In-browser audio preview player with seekbar and keyboard shortcuts (`Space`, `Esc`, arrow keys).

---

## 📁 Project Structure

```
listen-now/
├── main.py                 # FastAPI backend (Zero-disk stream piping engine)
├── requirements.txt        # Python dependencies
├── start.bat               # ⚡ Windows launcher (auto-setup & launch)
├── start.sh                # ⚡ Linux / macOS launcher
├── Dockerfile              # Docker image (includes FFmpeg & Python)
├── docker-compose.yml      # Docker Compose configuration
├── .gitignore
├── ffmpeg/
│   └── bin/
│       ├── ffmpeg.exe      # Bundled FFmpeg binary (Windows)
│       └── ffprobe.exe     # Bundled FFprobe binary (Windows)
├── venv/                   # Python virtual environment (auto-created)
└── static/
    ├── index.html          # Clean modular HTML structure
    ├── css/
    │   └── style.css       # Design tokens, responsive & dark theme styles
    ├── js/
    │   └── app.js          # Player, search, pagination, stream download logic
    ├── logo.png            # App logo
    ├── manifest.json       # PWA manifest
    └── sw.js               # Service Worker for offline app-shell caching
```

---

## 🚀 Getting Started

### ✅ Option 1 – Windows (Easiest) ⭐

Make sure **Python 3.11+** is installed, then:

```
Double-click → start.bat
```

The script will automatically:
- Create a virtual environment (`venv/`) if it doesn't exist
- Install all required dependencies
- Detect the bundled FFmpeg in `ffmpeg/bin/`
- Open the browser at http://localhost:8000

---

### ✅ Option 2 – Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

> **Note for Linux/macOS:** The `ffmpeg/bin/` folder contains Windows binaries (`.exe`).
> Install FFmpeg via your package manager:
> ```bash
> # Ubuntu / Debian
> sudo apt install ffmpeg
>
> # macOS (Homebrew)
> brew install ffmpeg
> ```

---

### ✅ Option 3 – Docker

```bash
docker-compose up --build
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Main page (frontend) |
| `GET` | `/api/health` | Health & active stream count |
| `GET` | `/api/storage` | Zero-disk statistics & active stream counters |
| `GET` | `/api/search?q=&limit=` | Fast YouTube search (default 10, max 50) |
| `GET` | `/api/preview?url=` | Extract direct audio stream URL for in-browser playback |
| `POST` | `/api/download` | Pre-resolve stream in ~0.5s & issue stream token |
| `GET` | `/api/stream?token=&url=` | Real-time on-the-fly audio streaming directly to browser |

---

## 🌐 Advanced Configuration (Proxy & Cookies)

To bypass YouTube bot detection or rate limits on cloud VPS hosts:
- **Cookies**: Place a `cookies.txt` file in the project root directory, or set `YTDLP_COOKIES_FILE=/path/to/cookies.txt`.
- **Proxy**: Set `YTDLP_PROXY=http://user:pass@host:port`.

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn, SlowAPI |
| Streaming Engine | yt-dlp + FFmpeg In-Memory Pipes (`pipe:1`) |
| Frontend | HTML5, Vanilla CSS3, Vanilla JS, PWA Service Worker |
| Container | Docker, Docker Compose |
