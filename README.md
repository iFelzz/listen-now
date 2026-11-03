# 🎵 Listen Now – YouTube MP3 Downloader

A modern full-stack web application to search for songs on YouTube, preview audio directly in the browser, and download high-quality MP3 files (128 / 192 / 320 kbps) with embedded cover art and metadata. Built with **FastAPI** + **yt-dlp** + **FFmpeg**.

> ✅ **Self-contained** – FFmpeg is bundled inside the project for Windows. Just clone/copy the folder and run `start.bat`.

---

## 📁 Project Structure

```
listen-now/
├── main.py                 # FastAPI backend (API endpoints & background workers)
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
├── downloads/              # Downloaded MP3 files (auto-cleaned)
│   └── README.md
└── static/
    ├── index.html          # Clean modular HTML structure
    ├── css/
    │   └── style.css       # Design tokens, responsive & dark theme styles
    ├── js/
    │   └── app.js          # Player, search, pagination, WebSocket logic
    ├── logo.png            # App logo
    ├── manifest.json       # PWA manifest
    └── sw.js               # Service Worker for offline app-shell caching
```

---

## 🚀 Getting Started

### ✅ Option 1 – Windows (Easiest) ⭐

Make sure **Python 3.10+** is installed, then:

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

### ✅ Option 3 – Manual (Terminal)

```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# or: source venv/bin/activate   # Linux / macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

### ✅ Option 4 – Docker

```bash
docker-compose up --build
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Main page (frontend) |
| `GET` | `/api/health` | Health check endpoint |
| `GET` | `/api/search?q=&limit=` | Search YouTube (default 10, max 50 results) |
| `GET` | `/api/preview?url=` | Extract direct audio stream URL for in-browser preview |
| `POST` | `/api/download` | Download audio and convert to MP3 (128 / 192 / 320 kbps) |
| `GET` | `/api/storage` | Storage usage statistics & cleanup configuration |
| `POST` | `/api/cleanup` | Manually trigger file & memory cache cleanup |
| `GET` | `/api/file/{filename}` | Safely serve downloaded MP3 with path traversal protection |
| `WS` | `/api/ws/progress/{client_id}` | WebSocket for real-time download and conversion progress |

### Example – Search Request
```http
GET /api/search?q=bohemian+rhapsody&limit=10
```

### Example – Download Request
```http
POST /api/download
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=fJ9rUzIMcZQ",
  "title": "Bohemian Rhapsody",
  "quality": "192",
  "client_id": "optional-uuid"
}
```

---

## 🧹 Auto-Cleanup & Storage Management

Downloaded files and temporary caches are managed automatically to keep storage lean:

| Setting | Default | Description |
|---|---|---|
| `MAX_AGE_HOURS` | `1` | Delete MP3 files older than 1 hour |
| `MAX_STORAGE_MB` | `500` | Delete oldest files if total folder exceeds 500 MB |
| `CLEANUP_INTERVAL` | `30` | Run background cleanup every 30 minutes |
| `CLEANUP_TOKEN` | *(optional)* | Secret token required to trigger `POST /api/cleanup` |

---

## 🌐 Advanced Configuration (Proxy & Cookies)

To bypass YouTube bot detection or rate limits on cloud VPS hosts:
- **Cookies**: Place a `cookies.txt` file in the project root directory, or set the `YTDLP_COOKIES_FILE=/path/to/cookies.txt` environment variable.
- **Proxy**: Set the `YTDLP_PROXY=http://user:pass@host:port` environment variable.

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, FastAPI, Uvicorn, SlowAPI |
| Downloader | yt-dlp |
| Converter | FFmpeg (bundled in `ffmpeg/` for Windows) |
| Frontend | HTML5, Vanilla CSS3, Vanilla JS, WebSockets, PWA Service Worker |
| Container | Docker, Docker Compose |
