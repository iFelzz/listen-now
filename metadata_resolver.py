"""
Metadata Resolver for Listen Now
─────────────────────────────────
Automatically fetches official cover art (800x800) and cleans song metadata
using a 3-tier hierarchy:
  1. YouTube Music official tags (track, artist, album)
  2. Apple iTunes Search API (studio 1:1 square album art, album name, year)
  3. YouTube MaxRes thumbnail fallback
"""

import re
import json
import logging
import urllib.parse
import urllib.request
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# Patterns commonly added to YouTube video titles that are not part of the song title
_NOISE_PATTERNS = [
    r"(?i)\[\s*official\s+music\s+video\s*\]",
    r"(?i)\(\s*official\s+music\s+video\s*\)",
    r"(?i)\[\s*official\s+video\s*\]",
    r"(?i)\(\s*official\s+video\s*\)",
    r"(?i)\[\s*official\s+audio\s*\]",
    r"(?i)\(\s*official\s+audio\s*\)",
    r"(?i)\[\s*performance\s+video\s*\]",
    r"(?i)\(\s*performance\s+video\s*\)",
    r"(?i)\[\s*visualizer\s*\]",
    r"(?i)\(\s*visualizer\s*\)",
    r"(?i)\[\s*m/?v\s*\]",
    r"(?i)\(\s*m/?v\s*\)",
    r"(?i)\bM/?V\b",
    r"(?i)\[\s*lyrics?\s*\]",
    r"(?i)\(\s*lyrics?\s*\)",
    r"(?i)\[\s*color\s*coded\s*lyrics?\s*\]",
    r"(?i)\(\s*color\s*coded\s*lyrics?\s*\)",
    r"(?i)\[\s*audio\s*\]",
    r"(?i)\(\s*audio\s*\)",
    r"(?i)\[\s*pre-debut\s+song\s*\]",
    r"(?i)\(\s*pre-debut\s+song\s*\)",
    r"(?i)\[\s*karaoke\s*(version)?\s*\]",
    r"(?i)\(\s*karaoke\s*(version)?\s*\)",
    r"(?i)\b(4k|hd|1080p|720p)\b",
]

def clean_noise(text: str) -> str:
    """Strip video annotations like [MV], (Official Audio), (Lyrics), and all quote marks."""
    result = text
    for pat in _NOISE_PATTERNS:
        result = re.sub(pat, "", result)
    # Remove leftover empty brackets or parentheses: () or []
    result = re.sub(r"\(\s*\)|\[\s*\]", "", result)
    # Strip all ASCII and Unicode curly/straight quotes
    result = re.sub(r"[\u2018\u2019\u201a\u201b\u201c\u201d\u201e\u201f\'\"\`]", "", result)
    result = re.sub(r"\s+", " ", result).strip()
    return result

def parse_artist_and_title(raw_title: str, uploader: str = "") -> Tuple[str, str]:
    """
    Parse 'Artist - Title' from raw YouTube video title.
    Returns (artist, title).
    """
    cleaned = clean_noise(raw_title)

    # Check for separator ' - ' or ' – ' or ' — '
    separators = [" - ", " – ", " — ", " : "]
    for sep in separators:
        if sep in cleaned:
            parts = cleaned.split(sep, 1)
            artist = clean_noise(parts[0])
            title = clean_noise(parts[1])
            # If artist ends with 'VEVO' or 'Official', clean it
            artist = re.sub(r"(?i)\s*(vevo|official|channel)$", "", artist).strip()
            return artist, title

    # Fallback: clean uploader as artist
    clean_uploader = re.sub(r"(?i)\s*(vevo|official|channel|\s*-\s*topic)$", "", uploader).strip()
    return clean_uploader or "Unknown Artist", cleaned

def fetch_itunes_metadata(artist: str, title: str) -> Optional[Dict[str, Any]]:
    """
    Query Apple iTunes Search API for official studio metadata and 800x800 square cover art.
    Uses smart multi-candidate matching to avoid piano covers or unrelated artists.
    Free, no API key required, response time ~100-150ms.
    """
    # Clean query: strip hyphens and punctuation that iTunes interprets as NOT operators
    clean_art = re.sub(r"[\u2018\u2019\u201c\u201d\u2014\u2013'\"`\-_:;/]", " ", artist)
    clean_tit = re.sub(r"[\u2018\u2019\u201c\u201d\u2014\u2013'\"`\-_:;/]", " ", title)
    query = re.sub(r"\s+", " ", f"{clean_art} {clean_tit}").strip()
    if not query:
        return None

    encoded_query = urllib.parse.quote_plus(query[:100])
    url = f"https://itunes.apple.com/search?term={encoded_query}&entity=song&limit=5"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )

    try:
        with urllib.request.urlopen(req, timeout=3.5) as response:
            if response.status != 200:
                return None
            data = json.loads(response.read().decode("utf-8"))
            results = data.get("results", [])
            if not results:
                return None

            norm_artist = re.sub(r"[^a-zA-Z0-9]", "", artist).lower()
            norm_title  = re.sub(r"[^a-zA-Z0-9]", "", title).lower()

            best_item = None
            for item in results:
                item_artist = re.sub(r"[^a-zA-Z0-9]", "", item.get("artistName", "")).lower()
                item_track  = re.sub(r"[^a-zA-Z0-9]", "", item.get("trackName", "")).lower()

                # Strong match: artist contains our artist OR our artist contains item artist
                if norm_artist and (norm_artist in item_artist or item_artist in norm_artist):
                    if norm_title and (norm_title in item_track or item_track in norm_title):
                        best_item = item
                        break
                    elif not best_item:
                        best_item = item

            # If no artist match was found among candidates, reject iTunes candidates
            # rather than picking an unrelated cover / instrumental artist
            if not best_item:
                first_artist = re.sub(r"[^a-zA-Z0-9]", "", results[0].get("artistName", "")).lower()
                first_track  = re.sub(r"[^a-zA-Z0-9]", "", results[0].get("trackName", "")).lower()
                if norm_artist and norm_artist in first_artist:
                    best_item = results[0]
                elif norm_title and norm_title in first_track and len(norm_title) >= 4:
                    best_item = results[0]
                else:
                    return None

            raw_art = best_item.get("artworkUrl100", "")
            # Upgrade standard 100x100 artwork URL to high-res 800x800 square
            hi_res_art = raw_art.replace("100x100bb.jpg", "800x800bb.jpg") if raw_art else ""

            rel_date = best_item.get("releaseDate", "")
            year = rel_date[:4] if rel_date and len(rel_date) >= 4 else ""

            return {
                "title":      best_item.get("trackName") or title,
                "artist":     best_item.get("artistName") or artist,
                "album":      best_item.get("collectionName") or "",
                "year":       year,
                "poster_url": hi_res_art,
                "source":     "itunes",
            }
    except Exception as exc:
        logger.warning("iTunes search lookup error for '%s': %s", query, exc)
        return None

def resolve_best_poster(yt_info: dict) -> str:
    """Find highest resolution thumbnail from YouTube metadata."""
    thumbnails = yt_info.get("thumbnails") or []
    if thumbnails:
        # Sort by resolution/width descending
        sorted_thumbs = sorted(
            [t for t in thumbnails if t.get("url")],
            key=lambda t: t.get("width") or 0,
            reverse=True
        )
        if sorted_thumbs:
            return sorted_thumbs[0]["url"]

    # Fallback to direct maxres or hqdefault
    video_id = yt_info.get("id")
    if video_id:
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return yt_info.get("thumbnail") or ""

def resolve_rich_metadata(yt_info: dict, raw_title: str) -> Dict[str, Any]:
    """
    Main resolver combining yt-dlp info, iTunes API, and YouTube thumbnails.
    Guarantees clean title, artist, album, and high-res poster URL.
    """
    uploader = yt_info.get("uploader") or yt_info.get("channel") or ""
    parsed_artist, parsed_title = parse_artist_and_title(raw_title, uploader)

    # 1. Prefer official YouTube Music tags if available
    official_track  = yt_info.get("track")
    official_artist = yt_info.get("artist")
    official_album  = yt_info.get("album")

    query_artist = official_artist or parsed_artist
    query_title  = official_track or parsed_title

    # 2. Query iTunes Search API for official studio cover & metadata
    itunes_data = fetch_itunes_metadata(query_artist, query_title)
    if itunes_data and itunes_data.get("poster_url"):
        logger.info("Official iTunes album cover found for: %s - %s", itunes_data['artist'], itunes_data['title'])
        return itunes_data

    # 3. Fallback: YouTube cleaned metadata & highest resolution thumbnail
    fallback_poster = resolve_best_poster(yt_info)
    upload_date = yt_info.get("upload_date") or ""
    year = upload_date[:4] if len(upload_date) >= 4 else ""

    logger.info("Using YouTube thumbnail fallback for: %s - %s", query_artist, query_title)
    return {
        "title":      query_title,
        "artist":     query_artist,
        "album":      official_album or f"{query_title} - Single",
        "year":       year,
        "poster_url": fallback_poster,
        "source":     "youtube",
    }

