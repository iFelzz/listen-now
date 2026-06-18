# 🎵 Listen Now – YouTube MP3 Downloader

A full-stack web application to search for songs on YouTube and download them as high-quality MP3 files (192 kbps). Built with **FastAPI** + **yt-dlp** + **FFmpeg**.

> ✅ **Self-contained** – FFmpeg is bundled inside the project. Just copy the folder and run `start.bat`.

---

## 📁 Project Structure

```
listen-now/
├── main.py                 # FastAPI backend (all API endpoints)
├── requirements.txt        # Python dependencies
├── start.bat               # ⚡ Windows launcher (double-click to start)
├── start.sh                # ⚡ Linux / macOS launcher
├── Dockerfile              # Docker image (includes FFmpeg)
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
    ├── index.html          # Frontend (HTML + CSS + JS)
    └── logo.png            # App logo
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

| Method | Endpoint             | Description                                    |
|--------|----------------------|------------------------------------------------|
| `GET`  | `/`                  | Main page (frontend)                           |
| `GET`  | `/api/health`        | Health check                                   |
| `GET`  | `/api/search?q=`     | Search YouTube (returns top 6 results)         |
| `POST` | `/api/download`      | Download audio as MP3 (192 kbps)               |
| `GET`  | `/api/storage`       | Storage usage info & cleanup configuration     |
| `POST` | `/api/cleanup`       | Manually trigger file cleanup                  |
| `GET`  | `/downloads/{file}`  | Serve a downloaded MP3 file                    |

### Example – Search Request
```http
GET /api/search?q=bohemian+rhapsody&limit=6
```

### Example – Download Request
```http
POST /api/download
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=fJ9rUzIMcZQ",
  "title": "Bohemian Rhapsody"
}
```

---

## 🧹 Auto-Cleanup

Downloaded files are automatically managed to prevent storage from filling up:

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_AGE_HOURS` | `1` | Delete files older than 1 hour |
| `MAX_STORAGE_MB` | `500` | Delete oldest files if folder exceeds 500 MB |
| `CLEANUP_INTERVAL` | `30` | Run cleanup every 30 minutes |

You can override these via environment variables:
```bash
MAX_AGE_HOURS=2 MAX_STORAGE_MB=1000 uvicorn main:app ...
```

---

## ⚙️ Tech Stack

| Layer      | Technology                            |
|------------|---------------------------------------|
| Backend    | Python 3.10+, FastAPI, Uvicorn        |
| Downloader | yt-dlp                                |
| Converter  | FFmpeg 8.1.1 (bundled in `ffmpeg/`)   |
| Frontend   | HTML5, Vanilla CSS, Vanilla JS        |
| Container  | Docker, Docker Compose                |

---

## 📝 Notes

- MP3 files are saved in the `downloads/` folder and auto-cleaned after 1 hour.
- FFmpeg is **bundled** in `ffmpeg/bin/` — no separate FFmpeg installation needed on Windows.
- If a file has already been downloaded, the server serves it directly without re-processing (cache hit).
- To use on another PC: copy the entire folder, make sure Python is installed, then run `start.bat`.
