@echo off
title Listen Now - YouTube MP3 Downloader
color 0A

echo.
echo  ==========================================
echo   Listen Now - YouTube MP3 Downloader
echo   Powered by FastAPI + yt-dlp + FFmpeg
echo  ==========================================
echo.

:: ── Cek Python tersedia ──────────────────────────────────
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak ditemukan di sistem ini.
    echo         Download Python dari https://python.org
    pause
    exit /b 1
)

:: ── Buat venv jika belum ada ─────────────────────────────
if not exist "venv\Scripts\python.exe" (
    echo [SETUP] Membuat virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Gagal membuat virtual environment.
        pause
        exit /b 1
    )
)

:: ── Install/update dependencies ──────────────────────────
echo [SETUP] Memeriksa dependencies...
venv\Scripts\pip.exe install -r requirements.txt --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [ERROR] Gagal install dependencies.
    pause
    exit /b 1
)

:: ── Cek FFmpeg bundled ───────────────────────────────────
if exist "ffmpeg\bin\ffmpeg.exe" (
    echo [OK] FFmpeg bundled ditemukan.
) else (
    echo [WARN] FFmpeg bundled tidak ada, mencoba dari PATH sistem...
)

:: ── Jalankan server ──────────────────────────────────────
echo.
echo [START] Menjalankan server di http://localhost:8000
echo         Tekan Ctrl+C untuk menghentikan.
echo.

:: Buka browser setelah 2 detik
start "" cmd /c "timeout /t 2 >nul && start http://localhost:8000"

:: Jalankan uvicorn via venv
venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000 --reload

pause
