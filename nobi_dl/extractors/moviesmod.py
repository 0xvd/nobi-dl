from ..nobi_dl import ExtractorBase
from ..utils import (
    _parse_a_tag,
    _parse_a_tags,
    is_series,
    _search_regex,
    _og_thumbnail,
    _og_title,
    determine_ext,
    determine_filesize,
    random_id,
    _parse_resolution,
    fix_entries,
)
import re
import itertools


class MoviesModME(ExtractorBase):
    _IE_NAME = "Moviesmod"
    _VALID_URL = r"https://?moviesmod\.[^/]+/[^?&#]+"
    _SEARCH = True

    @property
    def host(self):
        return self.host_finder.moviemod()

    def parse_content(self, html):
        results = []
        for article in re.findall(r"<article[\s\S]+?<\/article>", html):
            href = _search_regex(r'href="([^"]+)"', article)
            href = f"{self.host}{href}" if "https" not in href else href
            thumbnail = _search_regex(r'src="([^"]+)"', article)
            thumbnail = (
                f"{self.host}{thumbnail}" if "https" not in thumbnail else thumbnail
            )
            title = _search_regex(r'title="([^"]+)"', article)
            results.append(
                {
                    "title": title,
                    "thumbnail": thumbnail,
                    "url": href,
                    "quality": _parse_resolution(title),
                    "source": "hdhub",
                }
            )
        return results

    def _real_search(self, query, limit=50):
        search_result = []
        for pagenum in itertools.count(1):
            page = self._download_webpage(
                f"{self.host}/search/{query}/page/{pagenum}",
                headers={"referer": f"{self.host}/"},
            )
            search_result.extend(self.parse_content(page))
            is_next = _search_regex(
                r'(?is)<a\s*class\s*=\s*"next[^>]+>\s*next\s*?(?:[^<]+)?<',
                page,
                default=False,
            )
            if is_next is False or search_result >= limit:
                break

        return search_result

    def _get_movie(self, url_or_webpage):
        if url_or_webpage.startswith("http") or "<html" not in url_or_webpage:
            webpage = self._download_webpage(url_or_webpage)
        else:
            webpage = url_or_webpage

        formats = []
        for h4 in re.findall(r"<h4[\s\S]+?<\/h4>[\s\S]+?<a[\s\S]+?<\/a>", webpage):
            h4_texts = _search_regex(r"(<h4[\s\S]+?<\/h4>)", h4)
            for atag in _parse_a_tags(h4):
                href, name = _parse_a_tag(atag)
                label = (name or "").lower()
                if not any(
                    k in label for k in ("download links", "download link", "d links")
                ):
                    continue
                formats.append(
                    {
                        "format_id": random_id(),
                        "url": href,
                        "acodec": True,
                        "vcodec": True,
                        "ext": determine_ext(href, href),
                        **determine_filesize(h4_texts),
                        **_parse_resolution(h4_texts),
                    }
                )

        return {
            "title": _og_title(webpage),
            "thumbnail": _og_thumbnail(webpage),
            "formats": formats,
        }

    def extract_h3_text(self, block):
        h3_text = _search_regex(r"<h3[\s\S]+?<\/h3>", block)
        h3_text = re.sub(r"<[^>]+", " ", h3_text)
        return h3_text

    def extract_episodes(self, url, h3_text, op_webpage):
        webpage = self._download_webpage(url)
        episodes = []
        op_title = _og_title(op_webpage)
        season = _search_regex(r"(?is)(?:season|s0|s)\s*(\d+)", h3_text)
        for atag in _parse_a_tags(webpage):
            href, name = _parse_a_tag(atag)
            label = (name or "").lower()
            if not any(k in label for k in ("episode", "episo", "sode")):
                continue
            if not any(k in href for k in ("modpro.blog", "unblockedgames.world")):
                continue
            if any(k in label for k in ("all episodes", "episodes batch", "batch")):
                continue
            if "episodes" in href:
                continue
            ep_code = _search_regex(r"(?is)(?:episode|ep|ep0)\s*(\d+)", name)
            episodes.append(
                {
                    "title": f"{op_title} - season {season} - ep{ep_code}",
                    "season": season,
                    "episode": ep_code,
                    "formats": [
                        {
                            "url": href,
                            "acodec": True,
                            "vcodec": True,
                            "ext": "mkv",
                            **determine_filesize(h3_text),
                            **_parse_resolution(h3_text),
                        }
                    ],
                }
            )

        return episodes

    def entries(self, block, h3tag, op_webpage):
        h3tag = h3tag if h3tag else self.extract_h3_text(block)
        entires = []
        for atag in _parse_a_tags(block):
            href, name = _parse_a_tag(atag)
            label = (name or "").lower()
            if not any(k in label for k in ("episode", "episode links")):
                continue
            entires.extend(self.extract_episodes(href, h3tag, op_webpage))

        return entires

    def _get_series(self, url_or_webpage, url):
        if url_or_webpage.startswith("http") or "<html" not in url_or_webpage:
            webpage = self._download_webpage(url_or_webpage)
        else:
            webpage = url_or_webpage
        entries = []
        blocks = re.findall(r"<h3[\s\S]+?<\/h3>[\s\S]+?<\/p>", webpage)
        for block in blocks:
            block = re.sub(r"<h3[\s\S]+?<\s*hr\s*>", "", block)
            if "<a" not in block:
                continue
            h3_text = self.extract_h3_text(block)
            if not any(k in h3_text.lower() for k in ("season", "s01", "s1")):
                continue
            entries.extend(self.entries(block, h3_text, webpage))

        entries = fix_entries(self, entries)
        return self.playlist_result(entries, url)

    def _real_extract(self, url):
        webpage = self._download_webpage(url)
        if is_series(url, webpage):
            return self._get_series(webpage, url)
        else:
            return self._get_movie(webpage)
