# 🎵 Listen Now – YouTube MP3 Downloader

Aplikasi web full-stack untuk mencari lagu di YouTube dan mendownloadnya sebagai file MP3 berkualitas tinggi (192 kbps). Dibangun dengan **FastAPI** + **yt-dlp** + **FFmpeg**.

> ✅ **Self-contained** – FFmpeg sudah dibundel di dalam project. Cukup copy folder ini dan jalankan `start.bat`.

---

## 🗂 Struktur Folder

```
listen-now/
├── main.py                 # FastAPI backend (semua endpoint API)
├── requirements.txt        # Python dependencies
├── start.bat               # ⚡ Launcher Windows (double-click untuk mulai)
├── start.sh                # ⚡ Launcher Linux/macOS
├── Dockerfile              # Image Docker (termasuk FFmpeg)
├── docker-compose.yml      # Konfigurasi Docker Compose
├── .gitignore
├── ffmpeg/
│   └── bin/
│       ├── ffmpeg.exe      # FFmpeg bundled (Windows)
│       └── ffprobe.exe     # FFprobe bundled (Windows)
├── venv/                   # Python virtual environment (auto-created)
├── downloads/              # Folder hasil download MP3
│   └── README.md
└── static/
    ├── index.html          # Frontend (HTML + CSS + JS)
    └── logo.png            # Logo aplikasi
```

---

## 🚀 Cara Menjalankan

### ✅ Opsi 1 – Windows (Paling Mudah) ⭐

Pastikan **Python 3.10+** sudah terinstall, lalu:

```
Double-click → start.bat
```

Script akan otomatis:
- Membuat virtual environment (`venv/`) jika belum ada
- Menginstall semua dependencies
- Mendeteksi FFmpeg bundled di `ffmpeg/bin/`
- Membuka browser ke http://localhost:8000

---

### ✅ Opsi 2 – Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

> **Catatan untuk Linux/macOS:** Folder `ffmpeg/bin/` berisi binary Windows (`.exe`).  
> Install FFmpeg via package manager:
> ```bash
> # Ubuntu/Debian
> sudo apt install ffmpeg
>
> # macOS (Homebrew)
> brew install ffmpeg
> ```

---

### ✅ Opsi 3 – Manual (Terminal)

```bash
# 1. Buat dan aktifkan virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
# atau: source venv/bin/activate   # Linux/macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Jalankan server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

### ✅ Opsi 4 – Docker

```bash
docker-compose up --build
```

---

## 📡 API Endpoints

| Method | Endpoint           | Deskripsi                              |
|--------|--------------------|----------------------------------------|
| `GET`  | `/`                | Halaman utama (frontend)               |
| `GET`  | `/api/health`      | Health check                           |
| `GET`  | `/api/search?q=`   | Cari 6 lagu teratas di YouTube         |
| `POST` | `/api/download`    | Download audio sebagai MP3 (192 kbps)  |
| `GET`  | `/downloads/{file}`| Unduh file MP3 yang sudah diproses     |

---

## ⚙️ Tech Stack

| Layer     | Teknologi                          |
|-----------|------------------------------------|
| Backend   | Python 3.10+, FastAPI, Uvicorn     |
| Downloader| yt-dlp                             |
| Converter | FFmpeg 8.1.1 (bundled di `ffmpeg/`)|
| Frontend  | HTML5, Vanilla CSS, Vanilla JS     |
| Container | Docker, Docker Compose             |

---

## 📝 Catatan

- File MP3 disimpan di folder `downloads/` dan dapat diakses langsung.
- FFmpeg sudah **dibundel** di `ffmpeg/bin/` — tidak perlu install FFmpeg terpisah di Windows.
- Jika file sudah pernah didownload, server langsung menyajikan ulang tanpa proses ulang (cache hit).
- Untuk share ke PC lain: copy seluruh folder, pastikan Python terinstall, lalu jalankan `start.bat`.
