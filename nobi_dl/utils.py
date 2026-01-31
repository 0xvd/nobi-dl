import base64
import json
import os
import re
import sys
import urllib.parse
from html import unescape
import difflib
import random
from .version import REPOSITORY

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None


DEFAULT = None

KNOWN_RESOLUTIONS = {
    256: 144,
    426: 240,
    640: 360,
    854: 480,
    960: 540,
    1280: 720,
    1600: 900,
    1920: 1080,
    2560: 1440,
    3840: 2160,
    144: 256,
    240: 426,
    360: 640,
    480: 854,
    540: 960,
    720: 1280,
    900: 1600,
    1080: 1920,
    1440: 2560,
    2160: 3840,
    0: 0,
    None: 0,
}

JUNK_C = re.compile(
    r"(?i)\b("
    r"blu ?ray|brrip|hdrip|webrip|web[- ]dl|hdtv|x264|x265|hevc|aac|ddp?5\.?1|atmos|"
    r"org|nf|proper|repack|uncut|full movie|movie|"
    r"hindi|english|bengali|tamil|telugu|dual audio|"
    r"mp4|mkv|"
    r"\d{3,4}p|\d{3,4}x\d{3,4}|4k|8k|"
    r"\d+(?:\.\d+)?\s?(?:gb|mb|mib)|\d+k|"
    r"note|use|download|manager|instant|direct|"
    r"idm|adm|g\s?direct|like|or|for|g|g-direct"
    r")\b"
)

YEAR_C = re.compile(r"\b(19\d{2}|20\d{2})\b")

SERIES_URL_PAT = re.compile(
    r"/(season-\d+|s\d+e\d+|episode-\d+|ep-?\d+|all-episodes)\b", re.I
)
STRONG_SERIES = re.compile(
    r"\b(s\d+\s*e\d+|season\s*\d+|episode\s*\d+|all\s+episodes|web\s*series)\b", re.I
)
MOVIE_HINTS = re.compile(r"\b(full\s*movie|bluray|brrip|hdrip|webrip|dvdrip)\b", re.I)

_UNITS = {
    "b": 1,
    "kb": 10**3,
    "mb": 10**6,
    "gb": 10**9,
    "tb": 10**12,
    "pb": 10**15,
    "kib": 2**10,
    "mib": 2**20,
    "gib": 2**30,
    "tib": 2**40,
    "pib": 2**50,
}

SIZE_RE = re.compile(
    r"(?i)\b(?:size|filesize)\s*[:=]\s*([\d.,]+)\s*(b|kb|mb|gb|tb|pb|kib|mib|gib|tib|pib)\b"
)
INLINE_SIZE_RE = re.compile(
    r"(?i)(?<![a-z0-9.-])\b([\d.]{1,6})\s*(gb|mb|kb|tb|pb|gib|mib|kib|tib|pib)\b"
)
BADGE_SIZE_RE = re.compile(
    r'(?i)<span[^>]*class="[^"]*badge-size[^"]*"[^>]*>\s*([\d.,]+)\s*(b|kb|mb|gb|tb|pb|kib|mib|gib|tib|pib)\s*</span>'
)
CONTENT_LEN_RE = re.compile(r"(?i)\bcontent-length\s*[:=]\s*(\d+)\b")

KNOWN_EXTENSIONS = {
    "mp4",
    "mkv",
    "mov",
    "webm",
    "flv",
    "avi",
    "m4v",
    "ogv",
    "mpg",
    "mpeg",
    "m3u8",
    "ts",
}


def _parse_resolution(webpage_or_url: str):
    q = _search_regex(r"\b(\d{3,4})p\b", webpage_or_url, default=None)
    if q:
        h = int(q)
        w = KNOWN_RESOLUTIONS.get(h)
        return {"height": h, "width": w} if w else {}

    q = _search_regex(
        r"(?is)<title[^>]*>.*?\b(\d{3,4})p\b", webpage_or_url, default=None
    )
    if q:
        h = int(q)
        w = KNOWN_RESOLUTIONS.get(h)
        return {"height": h, "width": w} if w else {}

    q = re.search(r"\b(\d{3,4})\s*[xX]\s*(\d{3,4})\b", webpage_or_url or "")
    if not q:
        return {}

    a, b = int(q.group(1)), int(q.group(2))
    if a in KNOWN_RESOLUTIONS and KNOWN_RESOLUTIONS[a] == b:
        return {"height": a, "width": b}
    if b in KNOWN_RESOLUTIONS and KNOWN_RESOLUTIONS[b] == a:
        return {"height": b, "width": a}
    return {}


def b64d(s: str) -> str:
    s = s.strip()
    s += "=" * (-len(s) % 4)
    return base64.b64decode(s).decode("utf-8", errors="replace")


def rot_letters(s: str, shift: int = 13) -> str:
    def _rot(c: str) -> str:
        o = ord(c)
        if 65 <= o <= 90:
            return chr((o - 65 + shift) % 26 + 65)
        if 97 <= o <= 122:
            return chr((o - 97 + shift) % 26 + 97)
        return c

    return re.sub(r"[A-Za-z]", lambda m: _rot(m.group(0)), s)


def decode_o(o_value: str, shift: int = 13) -> dict:
    x = b64d(o_value)
    x = b64d(x)
    x = rot_letters(x, shift=shift)
    x = b64d(x)
    return json.loads(x)


def shifter(o_value: str):
    for sh in range(1, 26):
        try:
            data = decode_o(o_value, shift=sh)
            if isinstance(data, dict) and data.get("o"):
                return data
        except Exception:
            pass
    return None


def clean_url(url):
    if "http" not in url:
        url = f"https://{url}"
    parts = urllib.parse.urlsplit(url)
    if not parts.scheme and not parts.netloc:
        return None
    full_url = f"https://{parts.netloc}"
    return full_url


def _search_regex(pattern, string, flags=0, group=None, default=DEFAULT):
    if string is None:
        m = None
    elif isinstance(pattern, (str, re.Pattern)):
        m = re.search(pattern, string, flags)
    else:
        m = None
        for p in pattern:
            m = re.search(p, string, flags)
            if m:
                break
    if m:
        if group is None:
            for g in m.groups():
                if g is not None:
                    return g
            return m.group(0)
        if isinstance(group, (list, tuple)):
            return tuple(m.group(g) for g in group)
        return m.group(group)

    return default


def movie_keys(title: str) -> tuple[str, str]:
    t = (title or "").lower()
    y = YEAR_C.search(t)
    year = y.group(1) if y else ""
    if year:
        t = t.replace(year, " ")
    t = JUNK_C.sub(" ", t)
    t = re.sub(r"[\[\]\(\)\|:]", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    return t, year


def norm_title(s: str, only_lower=False) -> str:
    if only_lower is True:
        return s.lower()
    s = (s or "").lower()
    s = s.replace("’", "'")
    s = re.sub(r"'s\b", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _parse_a_tags(html):
    return re.findall(r"<a[\s\S]+?<\/a>", html)


def token_set_ratio(a: str, b: str) -> int:
    if fuzz:
        return int(fuzz.token_set_ratio(a, b))

    sa = " ".join(sorted(set((a or "").lower().split())))
    sb = " ".join(sorted(set((b or "").lower().split())))
    return int(difflib.SequenceMatcher(None, sa, sb).ratio() * 100)


def _remove_duplicate(data: list, threshold=90):
    kept, keys = [], []
    for d in data:
        k, year = movie_keys(d.get("title", ""))

        def is_dup(prev):
            pk, py = prev
            if year and py and year != py:
                return False
            return token_set_ratio(k, pk) >= threshold

        if any(is_dup(prev) for prev in keys):
            continue

        kept.append(d)
        keys.append((k, year))
    return kept


def _parse_a_tag(s):
    m_href = re.search(r'href\s*=\s*["\']([^"\']+)["\']', s, re.I)
    if not m_href:
        return None, None

    href = unescape(m_href.group(1))

    inner = re.sub(r"<\s*/?\s*a[^>]*>", "", s, flags=re.I)
    inner = re.sub(r"<[^>]+>", " ", inner)
    text = " ".join(inner.split())

    return href, text


def _og_title(html):
    title = _search_regex(r"<title\s*>([^<]+)<", html, default=None)
    if not title:
        title = _search_regex(r'<meta.+title".+content\s*=\s*"([^"]+)"', html)
    title = (title or "").strip()
    return title


def _get_qparam(
    url: str, keys: str | set[str] | list[str] | tuple[str, ...]
) -> str | None:
    if isinstance(keys, str):
        keys = (keys,)

    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query, keep_blank_values=False)
    for key in keys:
        vals = q.get(key)
        if not vals:
            continue
        v = vals[0]
        if v:
            return urllib.parse.unquote(v)
    return None


def get_tld(url_or_host: str) -> str | None:
    if "://" not in url_or_host:
        url_or_host = "http://" + url_or_host

    host = urllib.parse.urlparse(url_or_host).hostname
    if not host or "." not in host:
        return None

    parts = host.split(".")
    return "." + parts[-1]


def check_both_host_are_same(url: str, new_domain: str) -> str:
    tld1 = get_tld(url)
    tld2 = get_tld(new_domain)
    if tld1 != tld2:
        return True, url.replace(tld1, tld2)
    return False, None


def _og_thumbnail(html):
    thumbnail = _search_regex(r'<meta.+image".+content\s*=\s*"(https?[^"]+)"', html)
    if not thumbnail:
        thumbnail = _search_regex(r'thumbnail[^"]+"\s*:\s*"(http[^"]+)', html)
    return thumbnail


def _parse_m3u8_resolution(stream_inf_line: str):
    m = re.search(r"RESOLUTION=(\d+)x(\d+)", stream_inf_line)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def _m3u8_attr(tag_line: str, key: str):
    m = re.search(rf'{re.escape(key)}=("([^"]*)"|[^,]*)', tag_line)
    if not m:
        return None
    val = m.group(2) if m.group(2) is not None else m.group(1)
    return val.strip('"')


def _search_json(pattern, string, default=DEFAULT):
    m = _search_regex(pattern, string, default=default)
    if m:
        return json.loads(m)
    return default


def has_episode_structure(html: str) -> bool:
    return len(re.findall(r"(episode\s*\d+|s\d+\s*e\d+)", html, re.I)) >= 3


def is_series(url: str, html: str) -> bool:
    url_l = (url or "").lower()

    if SERIES_URL_PAT.search(url_l):
        return True
    if re.search(r"full-movie\b|movie\b", url_l, re.I):
        return False

    parts = []
    for pat in (r"<title[^>]*>(.*?)</title>", r"<h1[^>]*>(.*?)</h1>"):
        m = re.search(pat, html, flags=re.I | re.S)
        if m:
            parts.append(m.group(1))

    head = re.sub(r"<[^>]+>", " ", " ".join(parts))
    head = re.sub(r"\s+", " ", head).lower()

    if STRONG_SERIES.search(head):
        return True

    chunk = re.sub(r"<[^>]+>", " ", html[:30000])
    chunk = re.sub(r"\s+", " ", chunk).lower()

    if STRONG_SERIES.search(chunk):
        return True

    if has_episode_structure(chunk):
        return True

    if MOVIE_HINTS.search(head) or MOVIE_HINTS.search(chunk):
        return False

    return False


def url_filename(u: str) -> str | None:
    try:
        path = urllib.parse.urlparse(u).path
        base = os.path.basename(path)
        base = urllib.parse.unquote(base).strip()
        return base or None
    except Exception:
        return None


def determine_filesize(src):
    if not src:
        return {}

    headers = None
    if hasattr(src, "headers"):
        headers = src.headers
    elif isinstance(src, dict):
        headers = src

    if headers:
        cl = headers.get("content-length") or headers.get("Content-Length")
        try:
            n = int(cl)
            if n > 0:
                return {"filesize": n}
        except Exception:
            pass

    text = (
        src.decode("utf-8", "ignore")
        if isinstance(src, bytes)
        else src
        if isinstance(src, str)
        else str(src)
    )

    m = CONTENT_LEN_RE.search(text)
    if m:
        return {"filesize": int(m.group(1))}

    m = BADGE_SIZE_RE.search(text)
    if m:
        num_s, unit = m.groups()
        unit = unit.lower()
        try:
            size = int(float(num_s.replace(",", "")) * _UNITS[unit])
            return {"filesize_approx": size}
        except Exception:
            return {}

    m = SIZE_RE.search(text)
    if m:
        num_s, unit = m.groups()
        try:
            size = int(float(num_s.replace(",", "")) * _UNITS[unit.lower()])
            return {"filesize_approx": size}
        except Exception:
            return {}

    m = INLINE_SIZE_RE.search(text)
    if m:
        num_s, unit = m.groups()
        try:
            size = int(float(num_s.replace(",", "")) * _UNITS[unit.lower()])
            return {"filesize_approx": size}
        except Exception:
            pass

    return {}


def determine_ext(
    url: str | None, other_text: str | None = None, default_ext: str = "mp4"
) -> str:
    def _pick_from(s: str | None) -> str | None:
        if not s:
            return None
        s = str(s).strip()
        s = s.split("?", 1)[0].split("#", 1)[0].rstrip("/")
        if "." not in s:
            return None
        ext = s.rsplit(".", 1)[-1].lower()
        if "google" in url:
            ext = "mkv"
        return ext if ext in KNOWN_EXTENSIONS else None

    return _pick_from(url) or _pick_from(other_text) or default_ext


def bug_reports_message(before=";"):
    msg = (
        f"please report this issue on https://github.com/{REPOSITORY}/issues?q=, "
        f"filling out the appropriate issue template. Confirm you are on the latest version."
    )

    before = (before or "").rstrip()
    if not before or before.endswith((".", "!", "?")):
        msg = msg[:1].upper() + msg[1:]
    return (before + " " if before else "") + msg


def ascii_color(text, code, enable=True):
    return f"\033[{code}m{text}\033[0m" if enable else text


def is_tty(stream):
    try:
        return stream.isatty()
    except Exception:
        return False


class NobiDLError(Exception):
    def __init__(self, msg, *, url=None, expected=False, cause=None, color=True):
        self.url = url
        self.expected = expected
        self.cause = cause
        self.orig_msg = str(msg)
        self.color = color
        super().__init__()
        self.args = (self._msg,)

    @property
    def _msg(self):
        tag = ascii_color("[Error]", "31", self.color and is_tty(sys.stderr))
        where = f": {self.url}" if self.url else ""
        caused = f" (caused by {self.cause!r})" if self.cause else ""
        tail = "" if self.expected else bug_reports_message(";")
        return f"{tag}{where}: {self.orig_msg}{caused}{tail}"

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name != "args" and hasattr(self, "orig_msg"):
            try:
                self.args = (self._msg,)
            except Exception:
                pass

    def __str__(self):
        return self._msg


def approx_filesize_from_tbr(tbr_kbps, duration):
    if not tbr_kbps or not duration:
        return None
    return int(float(tbr_kbps) * 1000 / 8 * float(duration))


# TODO Remove When needed
# def tbr_from_filesize(filesize_bytes: int, duration_sec: float) -> int | None:
#     if not filesize_bytes or not duration_sec:
#         return {}
#     filesize = (
#         filesize_bytes.get("filesize")
#         or filesize_bytes.get("filesize_approx")
#         or filesize_bytes
#     )
#     if not filesize:
#         return {}
#     tbr = int((filesize * 8) / duration_sec / 1000)
#     return {"tbr": tbr}

# TODO Remove When needed
# def duration_from_anywhere(text: str):
#     if not text:
#         return None

#     m = re.search(r'(?is)"duration"\s*:\s*"(?P<iso>PT[^"]+)"', text)
#     if m:
#         iso = m.group("iso").upper()
#         hh = int(re.search(r"(\d+)H", iso).group(1)) if re.search(r"(\d+)H", iso) else 0
#         mm = int(re.search(r"(\d+)M", iso).group(1)) if re.search(r"(\d+)M", iso) else 0
#         ss = int(re.search(r"(\d+)S", iso).group(1)) if re.search(r"(\d+)S", iso) else 0
#         return hh * 3600 + mm * 60 + ss

#     m = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?::(\d{2}))?(?!\d)", text)
#     if m:
#         a, b, c = m.group(1), m.group(2), m.group(3)
#         if c is None:
#             return int(a) * 60 + int(b)
#         return int(a) * 3600 + int(b) * 60 + int(c)

#     m = re.search(
#         r"(?is)\b(?:runtime|duration|run\s*time)\b[^0-9]{0,40}((\d{1,2})\s*(?:h|hr|hrs))?[^0-9]{0,10}(\d{1,3})\s*(?:m|min|mins)\b",
#         text,
#     )
#     if m:
#         h = int(m.group(2) or 0)
#         mm = int(m.group(3))
#         return h * 3600 + mm * 60

#     m = re.search(r"(?i)\b(\d{1,4})\s*(?:m|min|mins|minute|minutes)\b", text)
#     if m:
#         return int(m.group(1)) * 60

#     vals = re.findall(r"#EXTINF:([0-9]+(?:\.[0-9]+)?)", text)
#     if vals:
#         return sum(float(x) for x in vals)
#     if "#EXT-X-TARGETDURATION" in text:
#         td = re.search(r"#EXT-X-TARGETDURATION:(\d+)", text)
#         segs = sum(
#             1 for ln in text.splitlines() if ln.strip() and not ln.startswith("#")
#         )
#         if td and segs:
#             return int(td.group(1)) * segs

#     return None


def fix_entries(self, entries: list) -> list:
    fixed = {}

    for entry in entries:
        season = entry.get("season")
        episode = entry.get("episode")

        if not all((season, episode)):
            self.show_warning("Missing season/episode, skipping")
            continue

        key = (season, episode)

        if key not in fixed:
            fixed[key] = entry
        else:
            fixed[key]["formats"].extend(entry.get("formats", []))

    return list(fixed.values())


def random_id() -> str:
    return str(random.randint(1_000_000, 9_999_999))[:4]


def filename_from_title(title: str, url, ext=None) -> str:
    ext = determine_ext(url, title) if ext is None else ext
    norm_title, _ = movie_keys(title)
    title_ext = determine_ext(norm_title, norm_title)
    if title_ext:
        norm_title = norm_title.replace(title_ext, "")
    filename = f"{norm_title}.{ext}" if "." not in ext else norm_title + ext
    return filename
