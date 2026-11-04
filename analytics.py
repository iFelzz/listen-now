"""
Melodyxx — Lightweight Internal Analytics & Metrics Engine
Tracks bandwidth, stream counts, popular tracks, search trends, and concurrency
with zero-database in-memory storage and debounced JSON persistence.
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
ANALYTICS_FILE = BASE_DIR / "analytics.json"


class AnalyticsEngine:
    def __init__(self, persistence_file: Path = ANALYTICS_FILE):
        self.file_path = persistence_file
        self.started_at = time.time()
        self._dirty = False
        self._last_save = time.time()

        # In-memory metrics state
        self.data: Dict[str, Any] = {
            "total_streams": 0,
            "total_bytes_streamed": 0,
            "total_searches": 0,
            "total_artist_searches": 0,
            "total_previews": 0,
            "peak_concurrency": 0,
            "top_tracks": {},     # "Artist - Title": count
            "top_artists": {},    # "Artist Name": count
            "daily_stats": {},    # "YYYY-MM-DD": { streams, bytes, searches, previews }
            "history_created_at": datetime.now(timezone.utc).isoformat(),
        }

        self._load()

    def _today_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _get_today_bucket(self) -> dict:
        today = self._today_key()
        if today not in self.data["daily_stats"]:
            self.data["daily_stats"][today] = {
                "streams": 0,
                "bytes": 0,
                "searches": 0,
                "previews": 0,
            }
        # Keep only the last 30 days to ensure minimal disk footprint (<50 KB)
        if len(self.data["daily_stats"]) > 35:
            sorted_keys = sorted(self.data["daily_stats"].keys())
            for old_key in sorted_keys[:-30]:
                self.data["daily_stats"].pop(old_key, None)

        return self.data["daily_stats"][today]

    def _load(self) -> None:
        """Load persisted metrics from disk if present."""
        if self.file_path.exists():
            try:
                content = self.file_path.read_text(encoding="utf-8")
                loaded = json.loads(content)
                if isinstance(loaded, dict):
                    # Merge keys
                    for k in ("total_streams", "total_bytes_streamed", "total_searches",
                              "total_artist_searches", "total_previews", "peak_concurrency"):
                        if k in loaded:
                            self.data[k] = loaded[k]
                    if isinstance(loaded.get("top_tracks"), dict):
                        self.data["top_tracks"] = loaded["top_tracks"]
                    if isinstance(loaded.get("top_artists"), dict):
                        self.data["top_artists"] = loaded["top_artists"]
                    if isinstance(loaded.get("daily_stats"), dict):
                        self.data["daily_stats"] = loaded["daily_stats"]
                    if loaded.get("history_created_at"):
                        self.data["history_created_at"] = loaded["history_created_at"]
                    logger.info("Analytics data loaded successfully (%d streams recorded).", self.data["total_streams"])
            except Exception as exc:
                logger.warning("Could not read analytics file (%s). Starting fresh.", exc)

    def save(self, force: bool = False) -> None:
        """Debounced flush to disk (at most once every 15 seconds unless forced)."""
        now = time.time()
        if not self._dirty and not force:
            return
        if not force and (now - self._last_save) < 15:
            return

        try:
            self.file_path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
            self._dirty = False
            self._last_save = now
        except Exception as exc:
            logger.warning("Failed to save analytics file: %s", exc)

    # ── Metric Recording Methods ──────────────────────────────

    def record_search(self, query: str) -> None:
        """Record a single track search."""
        self.data["total_searches"] += 1
        self._get_today_bucket()["searches"] += 1
        self._dirty = True
        self.save()

    def record_artist_search(self, artist_name: str) -> None:
        """Record an artist search and increment popularity rank."""
        self.data["total_artist_searches"] += 1
        clean_name = artist_name.strip().title()
        if clean_name and len(clean_name) > 1:
            curr = self.data["top_artists"].get(clean_name, 0)
            self.data["top_artists"][clean_name] = curr + 1
            # Keep top 50 artists max
            if len(self.data["top_artists"]) > 50:
                sorted_artists = sorted(self.data["top_artists"].items(), key=lambda x: x[1], reverse=True)
                self.data["top_artists"] = dict(sorted_artists[:50])

        self._get_today_bucket()["searches"] += 1
        self._dirty = True
        self.save()

    def record_preview(self) -> None:
        """Record an in-browser audio preview playback."""
        self.data["total_previews"] += 1
        self._get_today_bucket()["previews"] += 1
        self._dirty = True
        self.save()

    def record_concurrency(self, active_count: int) -> None:
        """Update peak concurrency tracker."""
        if active_count > self.data.get("peak_concurrency", 0):
            self.data["peak_concurrency"] = active_count
            self._dirty = True

    def record_stream_chunk(self, bytes_count: int) -> None:
        """Accumulate streamed bytes."""
        if bytes_count > 0:
            self.data["total_bytes_streamed"] += bytes_count
            self._get_today_bucket()["bytes"] += bytes_count
            self._dirty = True

    def record_stream_complete(self, title: str, artist: str, bytes_streamed: int) -> None:
        """Record a successfully streamed and downloaded song."""
        self.data["total_streams"] += 1
        self._get_today_bucket()["streams"] += 1

        # Track popularity
        track_key = f"{artist.strip()} - {title.strip()}" if artist and artist != "Unknown Artist" else title.strip()
        if track_key:
            curr = self.data["top_tracks"].get(track_key, 0)
            self.data["top_tracks"][track_key] = curr + 1
            # Keep top 50 tracks max
            if len(self.data["top_tracks"]) > 50:
                sorted_tracks = sorted(self.data["top_tracks"].items(), key=lambda x: x[1], reverse=True)
                self.data["top_tracks"] = dict(sorted_tracks[:50])

        self._dirty = True
        self.save()

    # ── Summary & Reporting ───────────────────────────────────

    def get_summary(self, current_active_streams: int = 0) -> Dict[str, Any]:
        """Generate human-readable metrics report."""
        now = time.time()
        uptime_seconds = int(now - self.started_at)
        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s" if days else f"{hours}h {minutes}m {seconds}s"

        today_bucket = self._get_today_bucket()
        total_bytes = self.data["total_bytes_streamed"]
        mb_streamed = round(total_bytes / (1024 * 1024), 2)
        gb_streamed = round(total_bytes / (1024 * 1024 * 1024), 3)

        # Sort top tracks
        sorted_tracks = sorted(self.data["top_tracks"].items(), key=lambda x: x[1], reverse=True)[:10]
        top_tracks_list = [{"name": k, "streams": v} for k, v in sorted_tracks]

        # Sort top artists
        sorted_artists = sorted(self.data["top_artists"].items(), key=lambda x: x[1], reverse=True)[:10]
        top_artists_list = [{"name": k, "searches": v} for k, v in sorted_artists]

        return {
            "status": "healthy",
            "uptime_seconds": uptime_seconds,
            "uptime_human": uptime_str,
            "started_at": datetime.fromtimestamp(self.started_at, tz=timezone.utc).isoformat(),
            "active_streams": current_active_streams,
            "peak_concurrency": self.data.get("peak_concurrency", 0),
            "total_streams": self.data["total_streams"],
            "total_bytes_streamed": total_bytes,
            "total_mb_streamed": mb_streamed,
            "total_gb_streamed": gb_streamed,
            "total_searches": self.data["total_searches"],
            "total_artist_searches": self.data["total_artist_searches"],
            "total_previews": self.data["total_previews"],
            "today": {
                "date": self._today_key(),
                "streams": today_bucket.get("streams", 0),
                "mb_streamed": round(today_bucket.get("bytes", 0) / (1024 * 1024), 2),
                "searches": today_bucket.get("searches", 0),
                "previews": today_bucket.get("previews", 0),
            },
            "top_tracks": top_tracks_list,
            "top_artists": top_artists_list,
            "recent_days": self.data.get("daily_stats", {}),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.data["total_streams"] = 0
        self.data["total_bytes_streamed"] = 0
        self.data["total_searches"] = 0
        self.data["total_artist_searches"] = 0
        self.data["total_previews"] = 0
        self.data["peak_concurrency"] = 0
        self.data["top_tracks"].clear()
        self.data["top_artists"].clear()
        self.data["daily_stats"].clear()
        self.save(force=True)


# Global singleton instance
analytics = AnalyticsEngine()

