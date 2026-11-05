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
import time
import logging
import urllib.parse
import urllib.request
import concurrent.futures
from typing import Optional, Tuple, Dict, Any, List, Set

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

_ARTIST_EXTRAS_CACHE: Dict[str, Dict[str, str]] = {}

def resolve_artist_extras(name: str, itunes_id: str = "", genre: str = "") -> dict:
    """
    Resolve artist portrait photo and country origin.
    Uses Deezer for high-res portrait images and MusicBrainz / Wikidata for country and national flag emoji.
    Results are cached in memory for sub-millisecond retrieval.
    """
    photo = ""
    country_name = ""
    country_code = ""
    flag = ""

    clean_name = re.sub(r"[\u2018\u2019\u201c\u201d\u2014\u2013'\"`\-_:;/]", " ", name).strip()
    if not clean_name:
        return {"photo": "", "country": "", "country_code": "", "flag": ""}

    cache_key = f"{clean_name.lower()}::{itunes_id}"
    if cache_key in _ARTIST_EXTRAS_CACHE:
        return _ARTIST_EXTRAS_CACHE[cache_key]

    # 1. Deezer for high-res artist portrait photo
    try:
        d_url = f"https://api.deezer.com/search/artist?q={urllib.parse.quote(clean_name)}&limit=1"
        req = urllib.request.Request(d_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                d_data = json.loads(resp.read().decode("utf-8"))
                items = d_data.get("data", [])
                if items:
                    top_d = items[0]
                    top_name = top_d.get("name", "").lower()
                    if clean_name.lower() in top_name or top_name in clean_name.lower():
                        photo = top_d.get("picture_medium") or top_d.get("picture") or ""
    except Exception:
        pass

    # Fallback to Apple Music latest release artwork if Deezer portrait unavailable
    if not photo and itunes_id:
        try:
            it_url = f"https://itunes.apple.com/lookup?id={itunes_id}&entity=album&limit=1"
            it_req = urllib.request.Request(it_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(it_req, timeout=2.0) as resp:
                if resp.status == 200:
                    it_data = json.loads(resp.read().decode("utf-8"))
                    for r in it_data.get("results", []):
                        if r.get("wrapperType") == "collection":
                            raw_art = r.get("artworkUrl100", "")
                            if raw_art:
                                photo = raw_art.replace("100x100bb.jpg", "300x300bb.jpg")
                                break
        except Exception:
            pass

    # 2. MusicBrainz for Country
    try:
        mb_url = f'https://musicbrainz.org/ws/2/artist/?query=artist:%22{urllib.parse.quote(clean_name)}%22&fmt=json&limit=1'
        req = urllib.request.Request(mb_url, headers={"User-Agent": "Melodyxx/1.1.0 (melodyxx@app.local)"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                mb_data = json.loads(resp.read().decode("utf-8"))
                mb_artists = mb_data.get("artists", [])
                if mb_artists:
                    ar = mb_artists[0]
                    country_code = ar.get("country") or ""
                    country_name = ar.get("area", {}).get("name") or ""
                    # Handle city/subdivision without explicit country code
                    if not country_code and country_name:
                        us_areas = {"brooklyn", "new york", "los angeles", "chicago", "houston", "nashville", "atlanta", "miami", "seattle"}
                        uk_areas = {"london", "manchester", "liverpool", "birmingham", "glasgow"}
                        if country_name.lower() in us_areas:
                            country_code = "US"
                            country_name = f"{country_name}, United States"
                        elif country_name.lower() in uk_areas:
                            country_code = "GB"
                            country_name = f"{country_name}, United Kingdom"
    except Exception:
        pass

    if country_code and len(country_code) == 2:
        flag = "".join(chr(127397 + ord(c)) for c in country_code.upper() if "A" <= c <= "Z")
    elif not country_name:
        # Fallback to Wikidata
        try:
            w_url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={urllib.parse.quote(clean_name)}&language=en&format=json&limit=1"
            w_req = urllib.request.Request(w_url, headers={"User-Agent": "Melodyxx/1.1.0"})
            with urllib.request.urlopen(w_req, timeout=1.8) as resp:
                if resp.status == 200:
                    w_res = json.loads(resp.read().decode("utf-8")).get("search", [])
                    if w_res:
                        desc = w_res[0].get("description", "").lower()
                        nationalities = [
                            ("indonesian", "ID", "Indonesia"),
                            ("south korean", "KR", "South Korea"),
                            ("korean", "KR", "South Korea"),
                            ("american", "US", "United States"),
                            ("british", "GB", "United Kingdom"),
                            ("english", "GB", "United Kingdom"),
                            ("russian", "RU", "Russia"),
                            ("japanese", "JP", "Japan"),
                            ("brazilian", "BR", "Brazil"),
                            ("canadian", "CA", "Canada"),
                            ("australian", "AU", "Australia"),
                            ("thai", "TH", "Thailand"),
                            ("mexican", "MX", "Mexico"),
                            ("spanish", "ES", "Spain"),
                            ("german", "DE", "Germany"),
                            ("french", "FR", "France"),
                            ("italian", "IT", "Italy"),
                            ("swedish", "SE", "Sweden"),
                            ("norwegian", "NO", "Norway"),
                            ("chinese", "CN", "China"),
                            ("taiwanese", "TW", "Taiwan"),
                        ]
                        for nat, ccode, cname in nationalities:
                            if nat in desc:
                                country_code = ccode
                                country_name = cname
                                flag = "".join(chr(127397 + ord(c)) for c in ccode.upper())
                                break
        except Exception:
            pass

    # Fallback to distinctive regional genre tags if country is still unknown
    if not country_name and genre:
        g_low = genre.lower()
        if "cantopop" in g_low or "hk-pop" in g_low or "hong kong" in g_low:
            country_code, country_name, flag = "HK", "Hong Kong", "🇭🇰"
        elif "k-pop" in g_low or "korean" in g_low:
            country_code, country_name, flag = "KR", "South Korea", "🇰🇷"
        elif "j-pop" in g_low or "j-rock" in g_low or "japanese" in g_low:
            country_code, country_name, flag = "JP", "Japan", "🇯🇵"
        elif "mandopop" in g_low or "chinese" in g_low:
            country_code, country_name, flag = "CN", "China", "🇨🇳"
        elif "dangdut" in g_low or "indonesian" in g_low:
            country_code, country_name, flag = "ID", "Indonesia", "🇮🇩"

    res = {
        "photo": photo or "",
        "country": country_name or "",
        "country_code": country_code or "",
        "flag": flag or "",
    }
    _ARTIST_EXTRAS_CACHE[cache_key] = res
    if len(_ARTIST_EXTRAS_CACHE) > 1000:
        _ARTIST_EXTRAS_CACHE.pop(next(iter(_ARTIST_EXTRAS_CACHE)), None)
    return res

# Common artist acronyms, aliases & nicknames for flexible search
ARTIST_ALIASES: Dict[str, List[str]] = {
    "h2h": ["Hearts2Hearts", "Heart2Heart", "Heart to Heart"],
    "hearts2hearts": ["Hearts2Hearts"],
    "bmth": ["Bring Me The Horizon"],
    "rhcp": ["Red Hot Chili Peppers"],
    "bep": ["Black Eyed Peas"],
    "snsd": ["Girls' Generation"],
    "gidle": ["(G)I-DLE"],
    "(g)i-dle": ["(G)I-DLE"],
    "g-idle": ["(G)I-DLE"],
    "mcr": ["My Chemical Romance"],
    "lp": ["Linkin Park"],
    "soad": ["System of a Down"],
    "fob": ["Fall Out Boy"],
    "foa": ["Fall Out Boy"],
    "ftp": ["Foster the People"],
    "top": ["Twenty One Pilots"],
    "t-o-p": ["Twenty One Pilots"],
    "cas": ["Cigarettes After Sex"],
    "casi": ["Cigarettes After Sex"],
    "akb": ["AKB48"],
    "akb48": ["AKB48"],
    "jkt": ["JKT48"],
    "jkt48": ["JKT48"],
    "bts": ["BTS"],
    "txt": ["TOMORROW X TOGETHER"],
    "svt": ["SEVENTEEN"],
    "skz": ["Stray Kids"],
    "nj": ["NewJeans"],
    "nwjns": ["NewJeans"],
    "lsf": ["LE SSERAFIM"],
    "lesserafim": ["LE SSERAFIM"],
    "rv": ["Red Velvet"],
    "bp": ["BLACKPINK"],
    "exo": ["EXO"],
    "nct": ["NCT", "NCT 127", "NCT DREAM"],
    "tbz": ["THE BOYZ"],
    "enhypen": ["ENHYPEN"],
    "mgk": ["Machine Gun Kelly"],
    "asap": ["A$AP Rocky", "A$AP Mob"],
    "a$ap": ["A$AP Rocky"],
    "ccr": ["Creedence Clearwater Revival"],
    "elo": ["Electric Light Orchestra"],
    "boc": ["Boards of Canada"],
    "tame": ["Tame Impala"],
    "posty": ["Post Malone"],
    "weeknd": ["The Weeknd"],
    "panic": ["Panic! At The Disco"],
    "patd": ["Panic! At The Disco"],
    "gorillaz": ["Gorillaz"],
    "daft": ["Daft Punk"],
    "chainsmokers": ["The Chainsmokers"],
    "dua": ["Dua Lipa"],
    "charli": ["Charli xcx"],
    "lana": ["Lana Del Rey"],
    "ariana": ["Ariana Grande"],
    "taylor": ["Taylor Swift"],
    "sabrina": ["Sabrina Carpenter"],
    "chappell": ["Chappell Roan"],
    "olivia": ["Olivia Rodrigo"],
    "billie": ["Billie Eilish"],
}

def get_artist_acronyms(name: str) -> Set[str]:
    """Extract possible acronyms/initialisms from artist name."""
    acrs = set()
    norm = name.strip()
    # 1. CamelCase & alphanumeric tokens: e.g. Hearts2Hearts -> ['Hearts', '2', 'Hearts']
    tokens = re.findall(r'[A-Z]+[a-z]*|[0-9]+|[a-z]+', norm)
    if len(tokens) > 1:
        acrs.add(''.join(t[0].lower() if not t.isdigit() else t for t in tokens))
        letters_only = ''.join(t[0].lower() for t in tokens if not t.isdigit())
        if len(letters_only) > 1:
            acrs.add(letters_only)
    # 2. Word tokens separated by spaces or punctuation: e.g. Bring Me The Horizon -> bmth
    words = [w for w in re.split(r'[\s\-_\.:;/\(\)&+]+', norm) if w]
    if len(words) > 1:
        acrs.add(''.join(w[0].lower() for w in words))
        sig = [w for w in words if w.lower() not in {"the", "of", "and", "a", "an", "in", "on", "at", "to", "for"}]
        if len(sig) > 1:
            acrs.add(''.join(w[0].lower() for w in sig))
    return acrs

def search_artists(query: str, limit: int = 24) -> dict:
    """
    Search artists via iTunes Search API with intelligent acronym/alias expansion,
    multi-query parallel search, and enriched portrait photos & nationality.
    Returns: {"results": [...], "suggestions": [...], "total": int}
    """
    clean_q = re.sub(r"[\u2018\u2019\u201c\u201d\u2014\u2013'\"`\-_:;/]", " ", query).strip()
    if not clean_q:
        return {"results": [], "suggestions": [], "total": 0}

    q_norm = clean_label_str(clean_q)

    # Gather search terms: primary query + any registered aliases
    search_terms = [clean_q]
    matched_aliases = ARTIST_ALIASES.get(q_norm, [])
    for alias in matched_aliases:
        if alias.lower() != clean_q.lower() and alias not in search_terms:
            search_terms.append(alias)

    def fetch_term(term: str) -> list:
        try:
            encoded = urllib.parse.quote_plus(term[:60])
            url = f"https://itunes.apple.com/search?term={encoded}&entity=musicArtist&limit={min(max(25, limit * 2), 50)}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8")).get("results", [])
        except Exception as e:
            logger.debug("iTunes search error for '%s': %s", term, e)
        return []

    raw_results = []
    if len(search_terms) == 1:
        raw_results = fetch_term(search_terms[0])
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(search_terms), 4)) as pool:
            for term_res in pool.map(fetch_term, search_terms):
                raw_results.extend(term_res)

    seen_ids = set()
    seen_names = set()
    exact_matches = []
    alias_acronym_matches = []
    partial_matches = []
    other_matches = []

    alias_norms = {clean_label_str(a) for a in matched_aliases}

    for r in raw_results:
        aid = r.get("artistId")
        name = r.get("artistName")
        if not aid or not name:
            continue

        aid_str = str(aid)
        norm_name = clean_label_str(name)

        if aid_str in seen_ids or norm_name in seen_names:
            continue
        seen_ids.add(aid_str)
        seen_names.add(norm_name)

        item = {
            "artist_id": aid_str,
            "name": name,
            "genre": r.get("primaryGenreName") or "Music",
            "artist_url": r.get("artistLinkUrl") or "",
        }

        artist_acrs = get_artist_acronyms(name)

        if norm_name == q_norm:
            exact_matches.append(item)
        elif norm_name in alias_norms or q_norm in artist_acrs:
            alias_acronym_matches.append(item)
        elif q_norm in norm_name or norm_name in q_norm:
            partial_matches.append(item)
        else:
            other_matches.append(item)

    # Combine prioritizing matches without discarding Apple's relevant results
    combined = exact_matches + alias_acronym_matches + partial_matches + other_matches
    final_results = combined[:limit]

    # Collect smart suggestions ("Did you mean?")
    suggestions = []
    for a in matched_aliases:
        if a.lower() != clean_q.lower() and a not in suggestions:
            suggestions.append(a)
    for it in alias_acronym_matches:
        if it["name"] not in suggestions and it["name"].lower() != clean_q.lower():
            suggestions.append(it["name"])

    # Enrich artists concurrently with high-res portrait photos & country
    if final_results:
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(final_results), 12)) as executor:
                extras_list = list(executor.map(
                    lambda it: resolve_artist_extras(it["name"], it.get("artist_id", ""), it.get("genre", "")),
                    final_results
                ))
                for item, extras in zip(final_results, extras_list):
                    item.update(extras)
        except Exception as enrich_err:
            logger.warning("Artist extras enrichment error: %s", enrich_err)

    return {
        "results": final_results,
        "suggestions": suggestions[:4],
        "total": len(final_results)
    }

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

    # Enrich with artist country, flag, and portrait photo
    if discography["name"]:
        try:
            extras = resolve_artist_extras(discography["name"], str(artist_id), discography.get("genre", ""))
            discography["country"] = extras.get("country", "")
            discography["country_code"] = extras.get("country_code", "")
            discography["flag"] = extras.get("flag", "")
            if extras.get("photo"):
                discography["photo"] = extras["photo"]
        except Exception:
            pass

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

_LIVE_SUGGEST_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_LIVE_SUGGEST_TTL = 600  # 10 minutes cache

def get_live_suggestions(query: str, mode: str = "songs") -> Dict[str, Any]:
    """
    Ultra-fast real-time search autocomplete & artist recommendations.
    Fetches real-time YouTube query predictions and iTunes artist data in parallel.
    Utilizes an in-memory TTL cache for instant (<1ms) responses on repeated queries.
    """
    clean_q = query.strip()
    if not clean_q:
        return {"query": "", "top_artist": None, "artists": [], "suggestions": []}

    cache_key = f"{mode}:{clean_q.lower()}"
    now = time.time()
    if cache_key in _LIVE_SUGGEST_CACHE:
        ts, data = _LIVE_SUGGEST_CACHE[cache_key]
        if now - ts < _LIVE_SUGGEST_TTL:
            return data

    q_norm = clean_label_str(clean_q)
    alias_matches = ARTIST_ALIASES.get(q_norm, [])

    def fetch_yt(term: str) -> List[str]:
        try:
            url = f"https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q={urllib.parse.quote(term)}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=1.8) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8"))
                    if isinstance(payload, list) and len(payload) > 1 and isinstance(payload[1], list):
                        return [s for s in payload[1] if isinstance(s, str)]
        except Exception as e:
            logger.debug("YouTube suggestion fetch error: %s", e)
        return []

    def fetch_itunes_artists(term: str, limit: int = 4) -> List[Dict[str, Any]]:
        try:
            url = f"https://itunes.apple.com/search?term={urllib.parse.quote_plus(term)}&entity=musicArtist&limit={limit}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=1.8) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8")).get("results", [])
        except Exception as e:
            logger.debug("iTunes artist lookup error: %s", e)
        return []

    # If searching in Artists mode, strictly return artists without YouTube song queries
    if mode == "artists":
        terms = [clean_q]
        if alias_matches:
            for al in alias_matches:
                if al not in terms:
                    terms.append(al)

        raw_artist_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(terms), 3)) as pool:
            for term_res in pool.map(lambda t: fetch_itunes_artists(t, limit=10), terms):
                raw_artist_results.extend(term_res)

        seen_ids = set()
        exact_matches = []
        prefix_matches = []
        other_matches = []

        for r in raw_artist_results:
            aid = r.get("artistId")
            aname = r.get("artistName")
            if not aid or not aname:
                continue
            aid_str = str(aid)
            if aid_str in seen_ids:
                continue
            seen_ids.add(aid_str)
            item = {
                "artist_id": aid_str,
                "name": aname,
                "genre": r.get("primaryGenreName") or "Artist",
                "artist_url": r.get("artistLinkUrl") or "",
            }
            anorm = clean_label_str(aname)
            if anorm == q_norm or (alias_matches and any(clean_label_str(alias) == anorm for alias in alias_matches)):
                exact_matches.append(item)
            elif anorm.startswith(q_norm) or q_norm in anorm:
                prefix_matches.append(item)
            else:
                other_matches.append(item)

        artists_list = exact_matches + prefix_matches + other_matches
        top_candidates = artists_list[:8]

        # Enrich artists concurrently with photo, country, and national flag
        if top_candidates:
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(top_candidates), 8)) as pool:
                    extras_list = list(pool.map(
                        lambda it: resolve_artist_extras(it["name"], it.get("artist_id", ""), it.get("genre", "")),
                        top_candidates
                    ))
                    for item, extras in zip(top_candidates, extras_list):
                        item.update(extras)
            except Exception as e:
                logger.debug("Artist extras error in live suggest: %s", e)

        result_data = {
            "mode": "artists",
            "query": clean_q,
            "top_artist": top_candidates[0] if top_candidates else None,
            "artists": top_candidates,
            "suggestions": []
        }
        _LIVE_SUGGEST_CACHE[cache_key] = (now, result_data)
        if len(_LIVE_SUGGEST_CACHE) > 500:
            oldest_key = min(_LIVE_SUGGEST_CACHE.keys(), key=lambda k: _LIVE_SUGGEST_CACHE[k][0])
            _LIVE_SUGGEST_CACHE.pop(oldest_key, None)
        return result_data

    yt_suggestions: List[str] = []
    itunes_artists_raw: List[Dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        f_yt = pool.submit(fetch_yt, clean_q)
        primary_itunes_term = alias_matches[0] if alias_matches else clean_q
        f_it = pool.submit(fetch_itunes_artists, primary_itunes_term)

        try:
            yt_suggestions = f_yt.result()
        except Exception:
            yt_suggestions = []

        try:
            itunes_artists_raw = f_it.result()
        except Exception:
            itunes_artists_raw = []

        # If top YouTube suggestion looks like an artist and differs from clean_q, check it
        top_candidate = yt_suggestions[0] if yt_suggestions else None
        if top_candidate and top_candidate.lower() != clean_q.lower() and len(top_candidate.split()) <= 3:
            has_exact = any(clean_label_str(r.get("artistName", "")) == clean_label_str(top_candidate) for r in itunes_artists_raw)
            if not has_exact:
                try:
                    f_top = pool.submit(fetch_itunes_artists, top_candidate)
                    top_raw = f_top.result()
                    if top_raw:
                        itunes_artists_raw = top_raw + itunes_artists_raw
                except Exception:
                    pass

    seen_ids = set()
    cleaned_artists: List[Dict[str, Any]] = []
    for r in itunes_artists_raw:
        aid = r.get("artistId")
        aname = r.get("artistName")
        if not aid or not aname:
            continue
        aid_str = str(aid)
        if aid_str in seen_ids:
            continue
        seen_ids.add(aid_str)
        cleaned_artists.append({
            "artist_id": aid_str,
            "name": aname,
            "genre": r.get("primaryGenreName") or "Artist",
            "artist_url": r.get("artistLinkUrl") or "",
        })

    best_artist = None
    for a in cleaned_artists:
        anorm = clean_label_str(a["name"])
        if alias_matches and any(clean_label_str(alias) == anorm for alias in alias_matches):
            best_artist = a
            break
        if anorm == q_norm or anorm.startswith(q_norm) or q_norm in anorm:
            best_artist = a
            break
        if yt_suggestions and anorm == clean_label_str(yt_suggestions[0]):
            best_artist = a
            break

    top_artist = best_artist or (cleaned_artists[0] if cleaned_artists else None)
    if top_artist:
        try:
            top_extras = resolve_artist_extras(top_artist["name"], top_artist.get("artist_id", ""), top_artist.get("genre", ""))
            top_artist.update(top_extras)
        except Exception:
            pass

    final_suggestions: List[str] = []
    seen_sugg = set()
    for s in yt_suggestions:
        s_clean = s.strip()
        s_low = s_clean.lower()
        if s_clean and s_low not in seen_sugg:
            seen_sugg.add(s_low)
            final_suggestions.append(s_clean)
        if len(final_suggestions) >= 8:
            break

    result_data = {
        "query": clean_q,
        "top_artist": top_artist,
        "artists": cleaned_artists[:4],
        "suggestions": final_suggestions
    }

    _LIVE_SUGGEST_CACHE[cache_key] = (now, result_data)
    if len(_LIVE_SUGGEST_CACHE) > 500:
        oldest_key = min(_LIVE_SUGGEST_CACHE.keys(), key=lambda k: _LIVE_SUGGEST_CACHE[k][0])
        _LIVE_SUGGEST_CACHE.pop(oldest_key, None)

    return result_data


