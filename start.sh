#!/usr/bin/env bash
# ──────────────────────────────────────────────
#  Listen Now - Startup Script (Linux / macOS)
# ──────────────────────────────────────────────

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo " =========================================="
echo "  Listen Now - YouTube MP3 Downloader"
echo "  Powered by FastAPI + yt-dlp + FFmpeg"
echo " =========================================="
echo ""

# ── Cek Python ──────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python3 tidak ditemukan. Install Python 3.10+ terlebih dahulu."
    exit 1
fi

# ── Buat venv jika belum ada ────────────────────────────
if [ ! -f "venv/bin/python" ]; then
    echo "[SETUP] Membuat virtual environment..."
    python3 -m venv venv
fi

# ── Install dependencies ─────────────────────────────────
echo "[SETUP] Memeriksa dependencies..."
venv/bin/pip install -r requirements.txt --quiet --disable-pip-version-check

# ── Cek FFmpeg ───────────────────────────────────────────
if [ -f "ffmpeg/bin/ffmpeg" ]; then
    echo "[OK] FFmpeg bundled ditemukan."
    export PATH="$SCRIPT_DIR/ffmpeg/bin:$PATH"
elif command -v ffmpeg &>/dev/null; then
    echo "[OK] FFmpeg ditemukan di PATH sistem."
else
    echo "[WARN] FFmpeg tidak ditemukan! Fitur download mungkin gagal."
fi

# ── Jalankan server ──────────────────────────────────────
echo ""
echo "[START] Menjalankan server di http://localhost:8000"
echo "        Tekan Ctrl+C untuk menghentikan."
echo ""

# Buka browser di background
(sleep 2 && (xdg-open http://localhost:8000 || open http://localhost:8000) 2>/dev/null) &

venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
