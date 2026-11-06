"""
Melodyxx — Lightweight Internal Analytics & Metrics Engine
Tracks bandwidth, stream counts, popular tracks, search trends, concurrency,
active user sessions (with IP and Country), and daily unique visitors
with zero-database in-memory storage and debounced JSON persistence.
"""

import json
import time
import logging
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
ANALYTICS_FILE = BASE_DIR / "analytics.json"

_GEO_CACHE: Dict[str, dict] = {}

_COUNTRY_NAMES = {
    "ID": "Indonesia", "US": "United States", "MY": "Malaysia", "SG": "Singapore",
    "JP": "Japan", "GB": "United Kingdom", "DE": "Germany", "AU": "Australia",
    "IN": "India", "KR": "South Korea", "CA": "Canada", "BR": "Brazil",
    "NL": "Netherlands", "PH": "Philippines", "VN": "Vietnam", "TH": "Thailand",
    "FR": "France", "IT": "Italy", "ES": "Spain", "RU": "Russia", "TR": "Turkey",
    "SA": "Saudi Arabia", "AE": "United Arab Emirates", "MX": "Mexico", "AR": "Argentina",
}


def country_code_to_flag(code: str) -> str:
    """Convert a 2-letter ISO country code into its emoji flag."""
    if not code or len(code) != 2:
        return "🌐"
    code = code.upper()
    try:
        return chr(ord(code[0]) + 127397) + chr(ord(code[1]) + 127397)
    except Exception:
        return "🌐"


def is_private_ip(ip: str) -> bool:
    """Check if an IP address is a loopback or private network IP."""
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return True
    if ip.startswith("10.") or ip.startswith("192.168.") or ip.startswith("172."):
        return True
    return False


def resolve_geo(ip: str, cf_country: Optional[str] = None) -> dict:
    """Resolve country, country code, and national flag from IP or Cloudflare header."""
    if not ip:
        return {"country": "Unknown", "country_code": "XX", "flag": "🌐"}

    # Cloudflare Country header provided (zero-latency in production)
    if cf_country and len(cf_country) == 2 and cf_country != "XX":
        code = cf_country.upper()
        cname = _COUNTRY_NAMES.get(code, code)
        return {"country": cname, "country_code": code, "flag": country_code_to_flag(code)}

    if ip in _GEO_CACHE:
        return _GEO_CACHE[ip]

    if is_private_ip(ip):
        res = {"country": "Localhost / Dev", "country_code": "LOC", "flag": "🏠"}
        _GEO_CACHE[ip] = res
        return res

    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,country,countryCode"
        req = urllib.request.Request(url, headers={"User-Agent": "Melodyxx-Analytics/1.0"})
        with urllib.request.urlopen(req, timeout=2.5) as r:
            payload = json.loads(r.read().decode("utf-8"))
            if payload.get("status") == "success":
                code = payload.get("countryCode", "XX")
                cname = payload.get("country", "Unknown")
                res = {
                    "country": cname,
                    "country_code": code,
                    "flag": country_code_to_flag(code),
                }
                _GEO_CACHE[ip] = res
                return res
    except Exception:
        pass

    res = {"country": "Unknown", "country_code": "XX", "flag": "🌐"}
    _GEO_CACHE[ip] = res
    return res


def parse_device_info(user_agent: str) -> str:
    """Parse basic OS and Browser from User-Agent string."""
    if not user_agent:
        return "Desktop • Browser"
    ua = user_agent.lower()

    # OS
    os_name = "Desktop"
    if "android" in ua:
        os_name = "Android"
    elif "iphone" in ua or "ipad" in ua:
        os_name = "iOS"
    elif "windows" in ua:
        os_name = "Windows"
    elif "macintosh" in ua or "mac os" in ua:
        os_name = "macOS"
    elif "linux" in ua:
        os_name = "Linux"

    # Browser
    browser = "Browser"
    if "edg/" in ua:
        browser = "Edge"
    elif "chrome/" in ua and "safari/" in ua and "edg/" not in ua:
        browser = "Chrome"
    elif "safari/" in ua and "chrome/" not in ua:
        browser = "Safari"
    elif "firefox/" in ua:
        browser = "Firefox"
    elif "opera/" in ua or "opr/" in ua:
        browser = "Opera"

    return f"{os_name} • {browser}"


class AnalyticsEngine:
    def __init__(self, persistence_file: Path = ANALYTICS_FILE):
        self.file_path = persistence_file
        self.started_at = time.time()
        self._dirty = False
        self._last_save = time.time()

        # In-memory transient active sessions (sliding window of 5 minutes)
        self.active_sessions: Dict[str, dict] = {}

        # Daily unique IP tracker { "YYYY-MM-DD": set(ips) }
        self.daily_ips: Dict[str, set] = {}

        # Persistent metrics state
        self.data: Dict[str, Any] = {
            "total_streams": 0,
            "total_bytes_streamed": 0,
            "total_searches": 0,
            "total_artist_searches": 0,
            "total_previews": 0,
            "total_unique_visitors": 0,
            "peak_concurrency": 0,
            "top_tracks": {},     # "Artist - Title": count
            "top_artists": {},    # "Artist Name": count
            "top_countries": {},  # "Country Name": count
            "daily_stats": {},    # "YYYY-MM-DD": { streams, bytes, searches, previews, unique_visitors }
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
                "unique_visitors": 0,
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
                              "total_artist_searches", "total_previews", "total_unique_visitors", "peak_concurrency"):
                        if k in loaded:
                            self.data[k] = loaded[k]
                    if isinstance(loaded.get("top_tracks"), dict):
                        self.data["top_tracks"] = loaded["top_tracks"]
                    if isinstance(loaded.get("top_artists"), dict):
                        self.data["top_artists"] = loaded["top_artists"]
                    if isinstance(loaded.get("top_countries"), dict):
                        self.data["top_countries"] = loaded["top_countries"]
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

    def record_activity(
        self,
        ip: str,
        action: str,
        cf_country: Optional[str] = None,
        user_agent: str = "",
    ) -> None:
        """Record a visitor interaction, resolve geo location, and track unique daily visitors."""
        now = time.time()
        today = self._today_key()

        # Track daily unique visitor
        if today not in self.daily_ips:
            self.daily_ips[today] = set()

        if ip not in self.daily_ips[today]:
            self.daily_ips[today].add(ip)
            today_bucket = self._get_today_bucket()
            today_bucket["unique_visitors"] = today_bucket.get("unique_visitors", 0) + 1
            self.data["total_unique_visitors"] = self.data.get("total_unique_visitors", 0) + 1
            self._dirty = True

        # Resolve Geo
        geo = resolve_geo(ip, cf_country)
        country_name = geo["country"]

        # Update top countries
        if country_name and country_name != "Localhost / Dev" and country_name != "Unknown":
            self.data["top_countries"][country_name] = self.data["top_countries"].get(country_name, 0) + 1
            self._dirty = True

        device = parse_device_info(user_agent)

        # Update active session
        prev = self.active_sessions.get(ip)
        action_count = (prev.get("action_count", 0) + 1) if prev else 1

        self.active_sessions[ip] = {
            "ip": ip,
            "country": country_name,
            "country_code": geo["country_code"],
            "flag": geo["flag"],
            "device": device,
            "last_action": action,
            "last_seen": now,
            "action_count": action_count,
        }

    def record_search(self, query: str, ip: str = "", cf_country: Optional[str] = None, user_agent: str = "") -> None:
        """Record a single track search."""
        self.data["total_searches"] += 1
        self._get_today_bucket()["searches"] += 1
        self._dirty = True
        if ip:
            self.record_activity(ip, f"Searching: {query[:35]}", cf_country, user_agent)
        self.save()

    def record_artist_search(self, artist_name: str, ip: str = "", cf_country: Optional[str] = None, user_agent: str = "") -> None:
        """Record an artist search and increment popularity rank."""
        self.data["total_artist_searches"] += 1
        clean_name = artist_name.strip().title()
        if clean_name and len(clean_name) > 1:
            curr = self.data["top_artists"].get(clean_name, 0)
            self.data["top_artists"][clean_name] = curr + 1
            if len(self.data["top_artists"]) > 50:
                sorted_artists = sorted(self.data["top_artists"].items(), key=lambda x: x[1], reverse=True)
                self.data["top_artists"] = dict(sorted_artists[:50])

        self._get_today_bucket()["searches"] += 1
        self._dirty = True
        if ip:
            self.record_activity(ip, f"Browsing Artist: {clean_name[:35]}", cf_country, user_agent)
        self.save()

    def record_preview(self, title: str = "", ip: str = "", cf_country: Optional[str] = None, user_agent: str = "") -> None:
        """Record an in-browser audio preview playback."""
        self.data["total_previews"] += 1
        self._get_today_bucket()["previews"] += 1
        self._dirty = True
        if ip:
            action_desc = f"Playing Preview: {title[:35]}" if title else "Listening Preview"
            self.record_activity(ip, action_desc, cf_country, user_agent)
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

    def record_stream_complete(
        self,
        title: str,
        artist: str,
        bytes_streamed: int,
        ip: str = "",
        cf_country: Optional[str] = None,
        user_agent: str = "",
        quality: str = "320",
    ) -> None:
        """Record a successfully streamed and downloaded song."""
        self.data["total_streams"] += 1
        self._get_today_bucket()["streams"] += 1

        # Track popularity
        clean_artist = artist.strip() if artist and artist != "Unknown Artist" else ""
        clean_title = title.strip()
        track_key = f"{clean_artist} - {clean_title}" if clean_artist else clean_title
        if track_key:
            curr = self.data["top_tracks"].get(track_key, 0)
            self.data["top_tracks"][track_key] = curr + 1
            if len(self.data["top_tracks"]) > 50:
                sorted_tracks = sorted(self.data["top_tracks"].items(), key=lambda x: x[1], reverse=True)
                self.data["top_tracks"] = dict(sorted_tracks[:50])

        self._dirty = True
        if ip:
            action_desc = f"Downloaded {quality}k MP3: {clean_title[:30]}"
            self.record_activity(ip, action_desc, cf_country, user_agent)
        self.save(force=True)

    # ── Summary & Reporting ───────────────────────────────────

    def get_summary(self, current_active_streams: int = 0) -> Dict[str, Any]:
        """Generate comprehensive real-time metrics report including active users and geography."""
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

        # Prune inactive sessions older than 5 minutes (300s)
        cutoff = now - 300
        active_ips = [ip for ip, s in self.active_sessions.items() if s.get("last_seen", 0) >= cutoff]
        self.active_sessions = {ip: self.active_sessions[ip] for ip in active_ips}

        # Build active user list sorted by most recent activity
        sorted_sessions = sorted(
            self.active_sessions.values(),
            key=lambda x: x.get("last_seen", 0),
            reverse=True
        )[:50]

        active_users_list = []
        for s in sorted_sessions:
            elapsed = int(now - s.get("last_seen", now))
            if elapsed < 10:
                human_seen = "Just now"
            elif elapsed < 60:
                human_seen = f"{elapsed}s ago"
            else:
                human_seen = f"{elapsed // 60}m ago"

            active_users_list.append({
                "ip": s.get("ip", ""),
                "country": s.get("country", "Unknown"),
                "country_code": s.get("country_code", "XX"),
                "flag": s.get("flag", "🌐"),
                "device": s.get("device", "Desktop • Browser"),
                "last_action": s.get("last_action", "Active"),
                "last_seen_human": human_seen,
                "action_count": s.get("action_count", 1),
            })

        # Sort top tracks
        sorted_tracks = sorted(self.data["top_tracks"].items(), key=lambda x: x[1], reverse=True)[:10]
        top_tracks_list = [{"name": k, "streams": v} for k, v in sorted_tracks]

        # Sort top artists
        sorted_artists = sorted(self.data["top_artists"].items(), key=lambda x: x[1], reverse=True)[:10]
        top_artists_list = [{"name": k, "searches": v} for k, v in sorted_artists]

        # Sort top countries
        sorted_countries = sorted(self.data.get("top_countries", {}).items(), key=lambda x: x[1], reverse=True)[:10]
        top_countries_list = []
        for cname, count in sorted_countries:
            code = next((k for k, v in _COUNTRY_NAMES.items() if v == cname), "")
            top_countries_list.append({
                "country": cname,
                "country_code": code,
                "flag": country_code_to_flag(code) if code else "🌐",
                "visits": count,
            })

        return {
            "status": "healthy",
            "uptime_seconds": uptime_seconds,
            "uptime_human": uptime_str,
            "started_at": datetime.fromtimestamp(self.started_at, tz=timezone.utc).isoformat(),
            "active_streams": current_active_streams,
            "active_users_count": len(self.active_sessions),
            "peak_concurrency": self.data.get("peak_concurrency", 0),
            "total_streams": self.data["total_streams"],
            "total_bytes_streamed": total_bytes,
            "total_mb_streamed": mb_streamed,
            "total_gb_streamed": gb_streamed,
            "total_searches": self.data["total_searches"],
            "total_artist_searches": self.data["total_artist_searches"],
            "total_previews": self.data["total_previews"],
            "total_unique_visitors": self.data.get("total_unique_visitors", 0),
            "today": {
                "date": self._today_key(),
                "streams": today_bucket.get("streams", 0),
                "mb_streamed": round(today_bucket.get("bytes", 0) / (1024 * 1024), 2),
                "searches": today_bucket.get("searches", 0),
                "previews": today_bucket.get("previews", 0),
                "unique_visitors": today_bucket.get("unique_visitors", 0),
            },
            "active_users": active_users_list,
            "top_tracks": top_tracks_list,
            "top_artists": top_artists_list,
            "top_countries": top_countries_list,
            "recent_days": self.data.get("daily_stats", {}),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.data["total_streams"] = 0
        self.data["total_bytes_streamed"] = 0
        self.data["total_searches"] = 0
        self.data["total_artist_searches"] = 0
        self.data["total_previews"] = 0
        self.data["total_unique_visitors"] = 0
        self.data["peak_concurrency"] = 0
        self.data["top_tracks"].clear()
        self.data["top_artists"].clear()
        self.data.get("top_countries", {}).clear()
        self.data["daily_stats"].clear()
        self.active_sessions.clear()
        self.daily_ips.clear()
        self.save(force=True)


# Global singleton instance
analytics = AnalyticsEngine()
