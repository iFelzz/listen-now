# ─────────────────────────────────────────────────────────────
#  Listen Now – Dockerfile
#  Base: python:3.10-slim  |  Includes: ffmpeg, yt-dlp, FastAPI
# ─────────────────────────────────────────────────────────────
FROM python:3.10-slim

# Metadata
LABEL maintainer="Listen Now"
LABEL description="YouTube MP3 Downloader powered by yt-dlp & FastAPI"

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ── System dependencies (ffmpeg is required by yt-dlp for audio conversion) ──
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ── Working directory ──
WORKDIR /app

# ── Python dependencies ──
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application source ──
COPY . .

# ── Create downloads directory ──
RUN mkdir -p /app/downloads

# ── Expose port ──
EXPOSE 8000

# ── Run the app ──
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
