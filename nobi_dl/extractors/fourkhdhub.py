import re
from nobi_dl.utils import (
    _search_regex,
    _parse_a_tag,
    _parse_a_tags,
    _og_thumbnail,
    _og_title,
    fix_entries,
    is_series,
    determine_ext,
    determine_filesize,
    _parse_resolution,
    random_id,
)
from .hdhub import Hdhub4uME
from nobi_dl import ExtractorBase


class FourkhdhubME(ExtractorBase):
    _IE_NAME = r"4khdhub"
    _VALID_URL = r"https://?4khdhub\.[^/]+/[^?&#]+"
    _SEARCH = True

    @property
    def HOST(self):
        return self.host_finder._4k_host()

    @property
    def hdhubme(self):
        return Hdhub4uME(self.md)

    def _clean_meta(self, meta: str) -> str:
        meta = (meta or "").strip()
        meta = re.compile(r"\s+").sub(" ", meta)
        meta = re.compile(r"\s*•\s*").sub(" • ", meta)
        return meta

    def _parse_search_4k_atags(self, atag: str, host: str):
        title = _search_regex(
            r'class="[^"]*movie[^"]*title[^"]*"\s*>\s*([^<]+?)\s*<', atag
        ).strip()
        meta = _search_regex(
            r'class="[^"]*movie[^"]*meta[^"]*"\s*>\s*([^<]+?)\s*<', atag
        ).strip()
        if meta:
            meta = self._clean_meta(meta)
        thumbnail = _search_regex(
            r'\bsrc="([^"]+)"[^>]*\bclass="[^"]*cover[^"]*"', atag
        ).strip()
        link = _search_regex(r'<a[^>]+href="([^"]+)"', atag).strip()
        year = _search_regex(r"\b(19\d{2}|20\d{2})\b", meta, default="").strip()
        if not link.startswith("http"):
            link = f"{host}{link}"

        return {
            "title": f"{title} - {meta}",
            "url": link,
            "thumbnail": thumbnail,
            "year": year,
            "quality": _parse_resolution(title),
            "source": "4khub",
        }

    def _real_search(self, query):
        webpage = self._download_webpage(f"{self.HOST}/?s={query}")
        results = []
        for atag in re.findall(
            r'(<a\s*href\s*=[^>]+class\s*="movie[^"]+"\s*>[\s\S]+?<\/a>)', webpage
        ):
            results.append(self._parse_search_4k_atags(atag, self.HOST))
        return results

    def _extract_formats(self, webpage):
        formats = []
        for filetag in re.findall(
            r'<div\s*class\s*=s*"file-title[^>]+>[\s\S]+?<\/div>\s*?<\/div>', webpage
        ):
            filelabel = _search_regex(r"\bfile-title[^>]+>([^<]+)<", filetag)
            filelabel_div = _search_regex(
                r"<div[^>]+\bfile-title[^>]+>[\s\S]+?<\/div>\s*[\s\S]+?<\/div>", filetag
            )
            for atag in _parse_a_tags(filetag):
                href, name = _parse_a_tag(atag)
                label = (name or "").lower()
                if not any(k in label for k in ("hubcloud", "download hubcloud")):
                    continue
                formats.append(
                    {
                        "format_id": random_id(),
                        "url": href,
                        "ext": determine_ext(filelabel, filelabel),
                        "acodec": True,
                        "vcodec": True,
                        **determine_filesize(filelabel_div),
                        **_parse_resolution(filelabel),
                    }
                )
        return formats

    def _get_movie(self, url_or_webpage):
        if "<html" in url_or_webpage:
            webpage = url_or_webpage
        else:
            webpage = self._download_webpage(url_or_webpage)

        w1, w2 = re.search(
            r"<span.*(?:Audios|audios)(?:[^\w]+(?P<w1>\w+\s*[^<]+))?(?:[^>]+>(?P<w2>[^<]+))",
            webpage,
        ).groups()
        languages = w2 if "span" in w1 else w1
        return {
            "title": _og_title(webpage),
            "languages": languages,
            "thumbnail": _og_thumbnail(webpage),
            "formats": self._extract_formats(webpage),
        }

    def entries(self, webpage):
        entries = []

        for season in re.findall(
            r'<div\s*class\s*=\s*"episode-download-item"?[^>]+?>[\s\S]+?<\/div>\s*<\/div>',
            webpage,
        ):
            format_id = _search_regex(r"\bfile-title[^>]+>([^<]+)<", season).strip()

            ep = _search_regex(r"(?is)(?:s\d+\s*)?(?:episode|ep|e)\s*(\d+)", format_id)
            season_num = _search_regex(r"(?is)(?:season|s0|s)\s*(\d+)", season) or "1"

            size = determine_filesize(season)
            ext = determine_ext(format_id)

            for atag in _parse_a_tags(season):
                href, name = _parse_a_tag(atag)
                label = (name or "").lower()

                if not any(k in label for k in ("hubcloud", "download hubcloud")):
                    continue

                entries.append(
                    {
                        "title": f"{format_id} - season {season_num} - ep {ep}",
                        "season": season_num,
                        "episode": ep,
                        "formats": [
                            {
                                "format_id": random_id(),
                                "url": href,
                                "acodec": True,
                                "vcodec": True,
                                "ext": ext,
                                **size,
                                **_parse_resolution(season),
                            }
                        ],
                    }
                )

        return entries

    def _get_series(self, url_or_webpage, url):
        if "<html" in url_or_webpage:
            webpage = url_or_webpage
        else:
            webpage = self._download_webpage(url_or_webpage)

        entires = fix_entries(self, self.entries(webpage))
        return self.playlist_result(entires, url, _og_title(webpage))

    def _real_extract(self, url):
        webpage = self._download_webpage(url)
        if is_series(url, webpage):
            return self._get_series(webpage, url)
        else:
            return self._get_movie(webpage)
