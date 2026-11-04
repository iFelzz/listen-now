"""
Metadata Resolver for Melodyxx
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
    r"(?i)\b(official\s+music\s+video|official\s+video|official\s+audio|music\s+video|lyric\s+video)\b",
    r"(?i)\b(official\s+mv|official\s+m/v)\b",
    r"(?i)\b(4k|hd|1080p|720p)\b",
]

QUOTE_CHARS = "'\"‘“’”`"

# Record label channels / publisher channels that should NEVER be attributed as the track artist
_LABEL_CHANNELS = {
    "smtown", "hybe labels", "hybe", "jyp entertainment", "jyp",
    "yg entertainment", "yg", "starshiptv", "starship", "1thek", "원더케이",
    "stone music entertainment", "stone music", "cube_official", "cube entertainment",
    "kq entertainment", "fnc official", "fnc entertainment", "pledis entertainment",
    "woollim", "mnet k-pop", "mnet", "all the k-pop", "studio choom", "kbs kpop",
    "bighit music", "belift lab", "source music", "ador", "wakeone",
    "genie music", "warnermusic", "warner records", "warner music",
    "sony music", "universal music", "spinnin' records", "monstercat",
    "trap nation", "lyrical lemonade", "ultra records", "vevo", "fueled by ramen",
    "atlantic records", "columbia records", "interscope records", "rca records",
    "def jam", "republic records", "epic records", "virgin music", "island records"
}

def clean_label_str(s: str) -> str:
    """Keep unicode letters and digits, strip whitespace and punctuation."""
    return re.sub(r"[^\w]", "", s, flags=re.UNICODE).lower()

def is_label_channel(name: str) -> bool:
    """Check if a channel / uploader name belongs to a record label or publisher."""
    if not name:
        return False
    norm = clean_label_str(name)
    if not norm:
        return False
    for label in _LABEL_CHANNELS:
        norm_label = clean_label_str(label)
        if not norm_label:
            continue
        # Exact match
        if norm_label == norm:
            return True
        # Substring match only if label is sufficiently specific (>= 4 chars)
        if len(norm_label) >= 4 and norm_label in norm:
            return True
        # For short 2-3 char labels like 'yg', 'jyp', match as whole token
        if len(norm_label) < 4:
            if re.search(rf"(?i)\b{re.escape(label)}\b", name):
                return True
    if re.search(r"(?i)\b(records|recordings|entertainment|labels|music group|publishing)\b", name):
        return True
    return False

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
    Parse (Artist, Title) from raw YouTube video title.
    Supports:
      1. Dash / colon separator: "Artist - Title", "Artist — Title"
      2. Quoted song title: "Artist 'Song Title' MV", "Artist 'Song's Title' Official Video"
      3. Uploader in title: "Artist Song Title"
      4. Fallback to uploader (skipping record labels)
    """
    # 1. Check for separator ' - ' or ' – ' or ' — ' or ' : '
    separators = [" - ", " – ", " — ", " : "]
    for sep in separators:
        if sep in raw_title:
            parts = raw_title.split(sep, 1)
            p_artist = clean_noise(parts[0])
            p_title  = clean_noise(parts[1])
            p_artist = re.sub(r"(?i)\s*(vevo|official|channel)$", "", p_artist).strip()
            # If the artist part is a record label (e.g. "SMTOWN - Red Velvet 'Psycho'"), check quotes in title
            if is_label_channel(p_artist):
                quote_indices = [i for i, c in enumerate(parts[1]) if c in QUOTE_CHARS]
                if len(quote_indices) >= 2:
                    cand_art = parts[1][:quote_indices[0]].strip()
                    cand_tit = parts[1][quote_indices[0]+1:quote_indices[-1]].strip()
                    if cand_art and cand_tit:
                        return clean_noise(cand_art), clean_noise(cand_tit)
                return "Unknown Artist", p_title
            return p_artist, p_title

    # 2. Check for quoted song title pattern:
    # e.g. Red Velvet 레드벨벳 'Surfin' Boy' MV
    # e.g. Red Velvet 레드벨벳 'Psycho' MV
    # e.g. aespa 에스파 'Supernova' MV
    # e.g. NewJeans (뉴진스) 'Super Shy' Official MV
    quote_indices = [i for i, c in enumerate(raw_title) if c in QUOTE_CHARS]
    if len(quote_indices) >= 2:
        q_start = quote_indices[0]
        q_end = quote_indices[-1]
        cand_artist = raw_title[:q_start].strip()
        cand_title  = raw_title[q_start+1:q_end].strip()
        if cand_artist and cand_title and len(cand_artist) <= 80:
            return clean_noise(cand_artist), clean_noise(cand_title)

    cleaned = clean_noise(raw_title)

    # 3. If uploader is known and not a record label
    if uploader and not is_label_channel(uploader):
        clean_up = clean_noise(re.sub(r"(?i)\s*(vevo|official|channel|\s*-\s*topic)$", "", uploader))
        if clean_up and clean_up.lower() in cleaned.lower():
            sub_title = re.sub(rf"(?i)\b{re.escape(clean_up)}\b", "", cleaned).strip()
            if sub_title:
                return clean_up, sub_title
        return clean_up or "Unknown Artist", cleaned

    return "Unknown Artist", cleaned

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

    # Never allow a record label channel name (e.g. SMTOWN, HYBE, JYP) to be the artist query
    if is_label_channel(query_artist):
        query_artist = official_artist or (parsed_artist if not is_label_channel(parsed_artist) else "Unknown Artist")

    # 2. Query iTunes Search API for official studio cover & metadata
    itunes_data = fetch_itunes_metadata(query_artist, query_title)
    if itunes_data and itunes_data.get("poster_url"):
        logger.info("Official iTunes album cover found for: %s - %s", itunes_data['artist'], itunes_data['title'])
        return itunes_data

    # 3. Fallback: YouTube cleaned metadata & highest resolution thumbnail
    fallback_poster = resolve_best_poster(yt_info)
    upload_date = yt_info.get("upload_date") or ""
    year = upload_date[:4] if len(upload_date) >= 4 else ""

    final_artist = query_artist if not is_label_channel(query_artist) else "Unknown Artist"

    logger.info("Using YouTube thumbnail fallback for: %s - %s", final_artist, query_title)
    return {
        "title":      query_title,
        "artist":     final_artist,
        "album":      official_album or (f"{query_title} - Single" if final_artist != "Unknown Artist" else ""),
        "year":       year,
        "poster_url": fallback_poster,
        "source":     "youtube",
    }

# ── Artist Discovery & Discography APIs ───────────────────────

def search_artists(query: str, limit: int = 10) -> list:
    """
    Search artists via iTunes Search API.
    Deduplicates identical artist names (keeping the top-ranked verified artist)
    and sorts exact/strong keyword matches first.
    """
    clean_q = re.sub(r"[\u2018\u2019\u201c\u201d\u2014\u2013'\"`\-_:;/]", " ", query).strip()
    if not clean_q:
        return []
    encoded = urllib.parse.quote_plus(clean_q[:60])
    url = f"https://itunes.apple.com/search?term={encoded}&entity=musicArtist&limit={min(max(20, limit * 3), 50)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            if resp.status != 200:
                return []
            data = json.loads(resp.read().decode("utf-8"))
            
            seen_names = set()
            exact_matches = []
            partial_matches = []
            other_matches = []
            
            q_norm = clean_label_str(clean_q)

            for r in data.get("results", []):
                aid = r.get("artistId")
                name = r.get("artistName")
                if not aid or not name:
                    continue

                norm_name = clean_label_str(name)
                # Deduplicate identical names (Apple ranks results by global popularity,
                # so the first occurrence is always the verified / primary artist)
                if norm_name in seen_names:
                    continue
                seen_names.add(norm_name)

                item = {
                    "artist_id": str(aid),
                    "name": name,
                    "genre": r.get("primaryGenreName") or "Music",
                    "artist_url": r.get("artistLinkUrl") or "",
                }

                if norm_name == q_norm:
                    exact_matches.append(item)
                elif q_norm in norm_name or norm_name in q_norm:
                    partial_matches.append(item)
                else:
                    other_matches.append(item)

            # Prioritize exact and partial matches, discarding unrelated noise
            if exact_matches or partial_matches:
                combined = exact_matches + partial_matches
            else:
                combined = other_matches

            return combined[:limit]
    except Exception as exc:
        logger.warning("Artist search error for '%s': %s", query, exc)
        return []

def normalize_track_key(title: str) -> str:
    """Normalize song title for deduplication while preserving distinct variations (remix, acoustic, live, etc.)."""
    s = title.lower().strip()
    s = re.sub(r"\s*(\[|\()(explicit|clean|remastered|remaster|digital\s+remaster|deluxe\s+edition|\d{4}\s+remaster)(\]|\))\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*[-–—]\s*(explicit|clean|remastered|remaster|\d{4}\s+remaster)\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[\'\"‘’“”`]", "", s)
    return re.sub(r"\s+", " ", s).strip()

def get_artist_discography(artist_id: str, limit_songs: int = 200, limit_albums: int = 50) -> dict:
    """
    Fetch top songs and albums for a given Apple Music artist ID.
    Supports up to 200 songs with smart deduplication favoring studio albums over singles.
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    discography = {
        "artist_id": str(artist_id),
        "name": "",
        "genre": "",
        "artwork_url": "",
        "top_songs": [],
        "albums": []
    }

    # 1. Fetch Top Songs
    songs_url = f"https://itunes.apple.com/lookup?id={artist_id}&entity=song&limit={limit_songs}"
    try:
        req = urllib.request.Request(songs_url, headers=headers)
        with urllib.request.urlopen(req, timeout=4.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                raw_songs = []
                for item in data.get("results", []):
                    wtype = item.get("wrapperType")
                    if wtype == "artist":
                        discography["name"] = item.get("artistName") or discography["name"]
                        discography["genre"] = item.get("primaryGenreName") or discography["genre"]
                    elif wtype == "track" and item.get("kind") == "song":
                        raw_art = item.get("artworkUrl100", "")
                        hi_art = raw_art.replace("100x100bb.jpg", "800x800bb.jpg") if raw_art else ""
                        if not discography["artwork_url"] and hi_art:
                            discography["artwork_url"] = hi_art

                        dur_sec = int(item.get("trackTimeMillis", 0) / 1000)
                        m, s = divmod(dur_sec, 60)
                        rel = item.get("releaseDate", "")
                        year = rel[:4] if rel and len(rel) >= 4 else ""

                        raw_songs.append({
                            "track_id": str(item.get("trackId", "")),
                            "title": item.get("trackName") or "",
                            "artist": item.get("artistName") or discography["name"],
                            "album": item.get("collectionName") or "",
                            "year": year,
                            "duration": f"{m}:{s:02d}",
                            "duration_sec": dur_sec,
                            "preview_url": item.get("previewUrl") or "",
                            "artwork_url": hi_art,
                            "track_number": item.get("trackNumber") or 1,
                        })

                unique_songs = {}
                for song in raw_songs:
                    key = normalize_track_key(song["title"])
                    album = (song.get("album") or "").lower()
                    if key not in unique_songs:
                        unique_songs[key] = song
                    else:
                        existing = unique_songs[key]
                        ex_album = (existing.get("album") or "").lower()
                        # Prefer studio album version over '- single' or '- ep'
                        if " - single" in ex_album and " - single" not in album:
                            unique_songs[key] = song
                        elif " - ep" in ex_album and (" - single" not in album and " - ep" not in album):
                            unique_songs[key] = song

                discography["top_songs"] = list(unique_songs.values())
    except Exception as exc:
        logger.warning("Error fetching top songs for artist %s: %s", artist_id, exc)

    # 2. Fetch Albums
    albums_url = f"https://itunes.apple.com/lookup?id={artist_id}&entity=album&limit={limit_albums}"
    try:
        req = urllib.request.Request(albums_url, headers=headers)
        with urllib.request.urlopen(req, timeout=4.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                for item in data.get("results", []):
                    if item.get("wrapperType") == "collection":
                        raw_art = item.get("artworkUrl100", "")
                        hi_art = raw_art.replace("100x100bb.jpg", "800x800bb.jpg") if raw_art else ""
                        rel = item.get("releaseDate", "")
                        year = rel[:4] if rel and len(rel) >= 4 else ""

                        discography["albums"].append({
                            "album_id": str(item.get("collectionId", "")),
                            "title": item.get("collectionName") or "",
                            "artist": item.get("artistName") or discography["name"],
                            "track_count": item.get("trackCount") or 0,
                            "year": year,
                            "genre": item.get("primaryGenreName") or discography["genre"],
                            "artwork_url": hi_art,
                        })
    except Exception as exc:
        logger.warning("Error fetching albums for artist %s: %s", artist_id, exc)

    discography["albums"].sort(key=lambda a: a.get("year", ""), reverse=True)
    return discography

def get_album_tracks(album_id: str) -> list:
    """
    Fetch all tracks for a specific album collection ID.
    """
    url = f"https://itunes.apple.com/lookup?id={album_id}&entity=song"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    tracks = []
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            if resp.status != 200:
                return []
            data = json.loads(resp.read().decode("utf-8"))
            album_art = ""
            album_name = ""
            album_artist = ""
            album_year = ""
            for item in data.get("results", []):
                if item.get("wrapperType") == "collection":
                    raw_art = item.get("artworkUrl100", "")
                    album_art = raw_art.replace("100x100bb.jpg", "800x800bb.jpg") if raw_art else ""
                    album_name = item.get("collectionName") or ""
                    album_artist = item.get("artistName") or ""
                    rel = item.get("releaseDate", "")
                    album_year = rel[:4] if rel and len(rel) >= 4 else ""
                elif item.get("wrapperType") == "track":
                    raw_art = item.get("artworkUrl100", "")
                    hi_art = (raw_art.replace("100x100bb.jpg", "800x800bb.jpg") if raw_art else "") or album_art
                    dur_sec = int(item.get("trackTimeMillis", 0) / 1000)
                    m, s = divmod(dur_sec, 60)
                    tracks.append({
                        "track_id": str(item.get("trackId", "")),
                        "track_number": item.get("trackNumber") or 1,
                        "title": item.get("trackName") or "",
                        "artist": item.get("artistName") or album_artist,
                        "album": item.get("collectionName") or album_name,
                        "year": album_year,
                        "duration": f"{m}:{s:02d}",
                        "duration_sec": dur_sec,
                        "preview_url": item.get("previewUrl") or "",
                        "artwork_url": hi_art,
                    })
            return tracks
    except Exception as exc:
        logger.warning("Error fetching album tracks for album %s: %s", album_id, exc)
        return []

