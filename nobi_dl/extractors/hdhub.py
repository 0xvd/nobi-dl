from ..host_finder import HOST_FINDER
import itertools
from html import unescape
import re
import ast
from nobi_dl.common import ExtractorBase
from nobi_dl.utils import (
    _remove_duplicate,
    _search_regex,
    _parse_a_tag,
    _parse_a_tags,
    shifter,
    b64d,
    is_series,
    _og_thumbnail,
    _search_json,
    _parse_resolution,
    _og_title,
    determine_filesize,
    determine_ext,
    random_id,
    fix_entries,
)


class Hdhub4uME(ExtractorBase):
    _IE_NAME = "hdhub4u"
    _VALID_URL = r"https://?[^\.]+\.hdhub4u[^/]+/[^?&#]+"
    _SEARCH = True

    _GLOBAL_SEEN_URLS = set()
    _VALID_DRIVE_URL = (
        r'(https?://[^"\s<>]*hubdrive[^"\s<>]*/(?:file/)?(?:\d+|[^"\s<>]+))'
    )
    _VALID_PIXEL_URL = r'(https?://[^"\s<>]*pixel[^"\s<>]*/(?:\d+|[^"\s<>]+))'
    _VALID_ARCHIVE_URL = r'(https?://[^"\s<>]*archives[^"\s<>]*/(?:\d+|[^"\s<>]+))'
    _VALID_HUBCLOUD_URL = (
        r'(https?://[^"\s<>]*cloud[^/\s<>]+/drive/(?!admin(?:/|$))[^"\s<>]+)'
    )

    @property
    def _search_host(self):
        return HOST_FINDER(self.md, self)._hdhub_search_host()

    def _real_search(self, query, limit=50):
        results = []

        for page in itertools.count(1):
            resp = self._download_json(
                f"{self._search_host}/collections/post/documents/search",
                query={
                    "q": query,
                    "query_by": "post_title,category,stars,director,imdb_id",
                    "limit": 15,
                    "use_cache": "true",
                    "page": page,
                    "highlight_fields": None,
                    "analytics_tag": "2026-01-17",
                    "query_by_weights": "4,2,2,2,4",
                },
                headers={
                    "referer": "https://hdhub4u.gd/",
                    "origin": "https://hdhub4u.gd",
                },
            )

            hits = resp.get("hits") or []
            for movie in hits:
                data = movie.get("document") or movie

                title = data.get("post_title")
                if not title:
                    continue

                url = data.get("permaurl")
                if not url:
                    continue

                if "https" not in url:
                    url = f"{self._search_host}{url}"

                results.append(
                    {
                        "title": title,
                        "url": url,
                        "thumbnail": data.get("post_thumbnail"),
                        "year": data.get("post_date"),
                        "quality": _parse_resolution(title),
                        "source": self._IE_NAME,
                    }
                )

            if resp.get("found") == len(results) or limit >= len(results):
                break

        return _remove_duplicate(results)

    def _hdhub_url_decoder(self, url):
        webpage = self._download_webpage(url, "Downloading challange webpage")
        o_token = _search_regex(
            r"""s\s*\(\s*['"]o['"]\s*,\s*['"]([^'"]+)['"]""", webpage, default=None
        )
        if not o_token:
            return None
        data = shifter(o_token)
        if not data:
            return None
        final_url = b64d(data["o"])
        return final_url

    def _minochinos_decoder_util(self, p: str, base: int, k: list[str]) -> str:
        DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"

        def base_n_to_int(s: str) -> int:
            n = 0
            for ch in s:
                n = n * base + DIGITS.index(ch)
            return n

        def repl(m: re.Match) -> str:
            tok = m.group(0)
            try:
                idx = base_n_to_int(tok)
            except ValueError:
                return tok
            if 0 <= idx < len(k) and k[idx]:
                return k[idx]
            return tok

        return re.sub(r"\b[0-9a-z]+\b", repl, p)

    def _parse_hubcloud(self, url):
        if (
            not _search_regex(self._VALID_HUBCLOUD_URL, url, default=None)
            or url in self._GLOBAL_SEEN_URLS
        ):
            return []
        self._GLOBAL_SEEN_URLS.add(url)
        webpage = self._download_webpage(url, "Downloading hubcloud information")
        cdns_url = _search_regex(
            r'<a[^>]+id\s*=\s*"download[^>]+href\s*=\s*"([^"]+)"[^>]*>[^<]*',
            webpage,
            default=None,
        )
        if not cdns_url:
            return []

        cdn_webpage = self._download_webpage(cdns_url)
        formats = []

        for a_tag in _parse_a_tags(cdn_webpage):
            href, _ = _parse_a_tag(a_tag)
            if not href:
                continue

            check = href.lower()
            if not any(k in check for k in ("pixel", "hubcdn", "fsl")):
                continue

            if _search_regex(self._VALID_PIXEL_URL, href, default=None):
                formats.append(
                    {
                        "format_id": random_id(),
                        "url": href,
                        "ext": determine_ext(href),
                        "acodec": True,
                        "vcodec": True,
                        **determine_filesize(webpage),
                        **_parse_resolution(webpage),
                    }
                )
            elif "fsl" in check:
                formats.append(
                    {
                        "format_id": random_id(),
                        "url": href,
                        "ext": determine_ext(href),
                        "acodec": True,
                        "vcodec": True,
                        **determine_filesize(webpage),
                        **_parse_resolution(webpage),
                    }
                )
        return formats

    def _parse_drive(self, url):
        if (
            not _search_regex(self._VALID_DRIVE_URL, url, default=None)
            or url in self._GLOBAL_SEEN_URLS
        ):
            return []
        self._GLOBAL_SEEN_URLS.add(url)
        webpage = self._download_webpage(url, "Downloading hubdrive information")
        hubcloud_url = _search_regex(self._VALID_HUBCLOUD_URL, webpage, default=None)
        phc = self._parse_hubcloud(hubcloud_url)
        return phc or []

    def _parse_archives(self, url):
        formats = []
        if (
            not _search_regex(self._VALID_ARCHIVE_URL, url, default=None)
            or url in self._GLOBAL_SEEN_URLS
        ):
            return []
        self._GLOBAL_SEEN_URLS.add(url)
        webpage = self._download_webpage(url, "Downloading hub archieve information")
        hub_url = _search_regex(self._VALID_HUBCLOUD_URL, webpage, default=None)
        if hub_url:
            hc = self._parse_hubcloud(hub_url)
        if hc:
            formats.extend(hc)
        return formats

    def _parse_formats(self, url):
        raw_formats = []
        if "drive.space" in url:
            raw_formats.extend(self._parse_drive(url))
        elif "/archives/" in url:
            raw_formats.extend(self._parse_archives(url))
        elif "cloud" in url:
            raw_formats.extend(self._parse_hubcloud(url))
        elif "pixel" in url:
            raw_formats.extend(self._parse_pixel(url))
        elif "hublinks" in url:
            raw_formats.extend(self.hublinks(url))
        if not raw_formats:
            return []
        formats = []
        seen_url = set()
        for quality in raw_formats:
            url = quality.get("url")
            if url in seen_url:
                continue
            seen_url.add(url)
            formats.append(quality)

        return formats

    def _minochinos_js_decoder(self, webpage: str):
        scripts = re.findall(
            r"<script\b[^>]*>(.*?)</script>", webpage, flags=re.DOTALL | re.I
        )
        js_text = next(
            (s for s in scripts if "eval(function(p,a,c,k,e,d)" in s.replace(" ", "")),
            None,
        )
        if not js_text:
            return None
        m = re.search(
            r"""eval\s*\(\s*function\s*\(\s*p\s*,\s*a\s*,\s*c\s*,\s*k\s*,\s*e\s*,\s*d\s*\)\s*\{.*?\}
                \s*\(\s*
                (?P<q1>['"])(?P<payload>(?:\\.|(?!\1).)*)(?P=q1)\s*,\s*
                (?P<base>\d+)\s*,\s*(?P<count>\d+)\s*,\s*
                (?P<q2>['"])(?P<dict>(?:\\.|(?!\4).)*)(?P=q2)\s*\.split\(\s*(?P<q3>['"])\|(?P=q3)\s*\)
                \s*\)\s*\)
            """,
            js_text,
            flags=re.DOTALL | re.VERBOSE | re.I,
        )
        if not m:
            return None

        p = ast.literal_eval(m.group("q1") + m.group("payload") + m.group("q1"))
        base = int(m.group("base"))
        k_raw = ast.literal_eval(m.group("q2") + m.group("dict") + m.group("q2"))
        k = k_raw.split("|")
        return self._minochinos_decoder_util(p, base, k)

    def _extract_player_formats(self, direct_url_or_webpage):
        formats = []
        if "stream" in direct_url_or_webpage and direct_url_or_webpage.startswith(
            "http"
        ):
            video_url = direct_url_or_webpage
        else:
            video_url = _search_regex(
                r'<a\b[^>]*href\s*=\s*["\'](https?://[^"\']*stream[^"\']*)["\']',
                direct_url_or_webpage,
            )
            if not video_url:
                return []
        video_webpage = self._download_webpage(video_url, "Downloading player url")
        title = _og_title(video_webpage)
        js_data = self._minochinos_js_decoder(video_webpage)
        if not js_data:
            self.show_warning("Unable to solve minochinos data")
            return []
        video_urls = _search_json(r"(?:urls|Urls)\s*=\s*(\{[\s\S]+?);", js_data)
        video_domain = _search_regex(
            r""">\s*[\s\S]+?(https.+)/(?:file|embed|download)/[^<"']""", video_webpage
        )
        video_domain = (
            f"http://{video_domain}" if "http" not in video_domain else video_domain
        )
        if not video_urls:
            return []
        for name, value in video_urls.items():
            if name.startswith("hls") and ".m3u8" in value:
                url = f"{video_domain}{value}" if "https" not in value else value
                formats.extend(self.extract_m3u8_formats(url, title))

        return formats

    def _get_movie(self, url_or_webpage):
        formats = []
        if "<html" in url_or_webpage:
            webpage = url_or_webpage
        else:
            webpage = self._download_webpage(url_or_webpage)

        languages = _search_regex(r'\bLanguage[^"]+?[^>]+>(.[^<]+)<', webpage)
        title = _search_regex(r'\bheadline\s*"\s*:\s*"([^"]+)"', webpage, default="")
        for a_tag in _parse_a_tags(webpage):
            href, text = _parse_a_tag(a_tag)
            valid_url = _search_regex(
                r'https?://(?!www\.googletagmanager\.com)[^"\s]+(?:\?id=[^"\s]+|/file/[^"\s]*)',
                href,
                default=None,
            )
            t = (text or "").strip().lower()
            if (
                t in ("watch online", "watch", "online", "hdhub4u")
                or href is None
                or not valid_url
            ):
                continue
            url = self._hdhub_url_decoder(href) if "id=" in href else href
            formats.extend(self._parse_formats(url))
        formats.extend(self._extract_player_formats(webpage))
        return {
            "title": title,
            "languages": languages,
            "thumbnail": _og_thumbnail(webpage),
            "formats": formats,
        }

    def hublinks(self, url):
        formats = []
        webpage = self._download_webpage(url, note="Download hublinks information")
        for h3_or_h5 in re.findall(r"<(?:h3|h5)[\s\S]+?<\/(?:h3|h5>)", webpage):
            h3_or_h5_title = _search_regex(r"<(?:h3|h5)[^>]+>([^<]+)<", h3_or_h5)
            if h3_or_h5_title:
                h3_or_h5_title = unescape(h3_or_h5_title.strip())
            if not h3_or_h5_title:
                continue
            for atag in _parse_a_tags(h3_or_h5):
                href, name = _parse_a_tag(atag)
                if any(k in href.lower() for k in ("hubcdn", "hubdrive")):
                    continue
                size = determine_filesize(name)
                if "hubcloud" in name.lower():
                    formats.extend(self._parse_hubcloud(href))
                elif size or "hubdrive" in href:
                    formats.append(
                        {
                            "format_id": random_id(),
                            "url": href,
                            "ext": "mkv",
                            "acodec": True,
                            "vcodec": True,
                            **size,
                            **_parse_resolution(name),
                        }
                    )

        return formats

    def diff_entries(self, webpage):
        valid_url_keys = ("drive", "hubdrive", "hdstream", "stream", "?id=", "hubcloud")
        entries = []
        title = _og_title(webpage)

        for atag in _parse_a_tags(webpage):
            href, name = _parse_a_tag(atag)
            if not href or not any(k in href for k in valid_url_keys):
                continue
            if name and "4k" in name.lower():
                continue
            href = self._hdhub_url_decoder(href) if "?id=" in href else href
            episode_formats = []
            episode_formats.extend(self._parse_formats(href))

            ep = _search_regex(
                r"(?is)(?:s\d+\s*)?(?:episode|ep|e)\s*(\d+)", name, default="1"
            )

            entries.append(
                {
                    "title": f"{title} - ep {ep}",
                    "season": 1,
                    "episode": int(ep),
                    "formats": episode_formats,
                }
            )

        return entries

    def entries(self, webpage):
        entries = []
        title = _og_title(webpage)

        blocks = re.split(r"<\s*hr\s*/?>", webpage, flags=re.I)

        for block in blocks:
            ep = _search_regex(r"(?i)episode\s*(\d+)", block, default=None)
            season = _search_regex(r"(?is)(?:season|s0|s)\s*(\d+)", block, default=1)
            if not ep:
                continue

            episode_formats = []

            for atag in _parse_a_tags(block):
                href, name = _parse_a_tag(atag)
                if not href or not name:
                    continue

                lname = name.lower()
                if lname not in ("drive"):
                    continue

                href = self._hdhub_url_decoder(href) if "?id=" in href else href

                episode_formats.extend(self._parse_formats(href))

            entries.append(
                {
                    "title": f"{title} - ep {ep}",
                    "season": season,
                    "episode": int(ep),
                    "formats": episode_formats,
                }
            )

        if not any(entry.get("formats") for entry in entries):
            return self.diff_entries(webpage)

        return entries

    def _get_series(self, url_or_webpage, url):
        if "<html" in url_or_webpage:
            webpage = url_or_webpage
        else:
            webpage = self._download_webpage(url_or_webpage)

        entries = fix_entries(self, self.entries(webpage))

        return self.playlist_result(
            entries,
            url,
            _og_title(webpage),
        )

    def _real_extract(self, url):
        webpage = self._download_webpage(url)

        if is_series(url, webpage):
            return self._get_series(webpage, url)
        else:
            return self._get_movie(webpage)
