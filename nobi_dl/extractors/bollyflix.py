from nobi_dl import ExtractorBase
import itertools
import re
from nobi_dl.utils import (
    _search_regex,
    clean_url,
    b64d,
    _parse_a_tag,
    _parse_a_tags,
    _og_title,
    is_series,
    _parse_resolution,
    _get_qparam,
    determine_ext,
    _og_thumbnail,
    determine_filesize,
)
from .hdhub import Hdhub4uME
from urllib.parse import quote_plus


class BollyFlixME(ExtractorBase):
    _IE_NAME = "Bollyflix"
    _VALID_URL = r"^https?://.*bollyflix\..+"
    _SEARCH = False

    @property
    def HOST(self):
        return self.host_finder.bollyflix()

    @property
    def hdhub4u(self):
        return Hdhub4uME(self.md)

    def _parse_content(self, html):
        results = []
        for article in re.findall(r"<article[\s\S]+?<\/article>", html):
            href = _search_regex(r'href="([^"]+)"', article)
            href = f"{self.HOST}{href}" if "https" not in href else href
            thumbnail = _search_regex(r'src="([^"]+)"', article)
            thumbnail = (
                f"{self.HOST}{thumbnail}" if "https" not in thumbnail else thumbnail
            )
            title = _search_regex(r'title="([^"]+)"', article)
            results.append(
                {
                    "title": title,
                    "thumbnail": thumbnail,
                    "url": href,
                    "acodec": True,
                    "vcodec": False,
                }
            )
        return results

    def _real_search(self, query):
        results = []
        for page in itertools.count(1):
            page = self._download_webpage(
                f"{self.HOST}/search/{quote_plus(query)}/page/{page}",
                headers={
                    "referer": "https://bollyflix.to/",
                },
            )
            results.extend(self._parse_content(page))
            next_page = _search_regex(r"<a[^>]+next[^>]+>Next<\/a>", page)
            if not next_page:
                break
        return results

    def _parse_formats(self, link, format_id=None):
        qualties = []
        webpage = self._download_webpage(link)
        title = _og_title(webpage)
        for atag in _parse_a_tags(webpage):
            href, name = _parse_a_tag(atag)
            format_id = (name or "").lower()
            if not any(
                k in format_id
                for k in ("instant", "fast cloud", "zipdisk", "pixel", "gofile")
            ):
                continue
            if "pixel" in format_id:
                qualties.extend(self.hdhub4u._parse_pixel(href, title))
            elif "instant" in format_id:
                req = self._request(href, method="HEAD")
                google_url = _get_qparam(req.url, "url")
                headers = self._request(google_url, method="HEAD").headers
                cd = headers.get("Content-Disposition", "")
                filename = _search_regex(r'filename\s*=\s*"([^"]+)"', cd)
                qualties.append(
                    {
                        "url": google_url,
                        "format_id": title or "instant dl",
                        **_parse_resolution(filename),
                        "ext": determine_ext(google_url),
                        "acodec": True,
                        "vcodec": False,
                        **determine_filesize(headers),
                    }
                )
            elif "zipdisk" in format_id:
                continue

        return qualties

    def bolly_url_decoder_resolver(self, url):
        webpage = self._download_webpage(url)
        out = []
        for p1, p2 in re.findall(
            r"""(?:'(?P<p1>[^']*)'\s*\+\s*)+'(?P<p2>[^']*)'?""", webpage
        ):
            parts = p1 + p2
            if "tech-news" in parts:
                out.append("https://box.tech-news.app")
            elif ".com" in parts:
                parts = f"https://{parts}" if "https" not in parts else parts
                out.append(parts)
        if not out:
            return None
        for domain in out:
            try:
                if self._ping_host(domain) == 200:
                    return domain
            except Exception:
                pass
        return out[0]

    def bolly_url_decoder(self, url):
        domain = self.bolly_url_decoder_resolver(url)
        if domain is None:
            webpage = self._download_webpage(url)
        token = _search_regex(r"\bid\s*=([^/?&#]+)", url)
        webpage = self._download_webpage(
            f"{domain}/?id={token}", headers={"referer": clean_url(url)}
        )
        e_token = _search_regex(r'\blink\s*?"\s*:\s*"([^"]+)', webpage)
        if not e_token:
            return None
        return b64d(e_token)

    def get_movie(self, url_or_webpage):
        formats = []
        if "<html" in url_or_webpage:
            webpage = url_or_webpage
        else:
            webpage = self._download_webpage(url_or_webpage)
        atags = _parse_a_tags(webpage)
        for atag in atags:
            href, name = _parse_a_tag(atag)
            format_id = (name or "").lower()
            if not any(
                k in format_id
                for k in ("google drive", "drive", "download links", "links")
            ):
                continue
            link = self.bolly_url_decoder(href) if "?id=" in href else href
            formats.extend(self._parse_formats(link))
        language = _search_regex(r'\bLanguage[^"]+?[^>]+>(.[^<]+)<', webpage)
        title = _search_regex(r'\bheadline\s*"\s*:\s*"([^"]+)"', webpage, default="")
        if not title:
            title = _og_title(webpage)
        return {
            "title": title,
            "thumbnail": _og_thumbnail(webpage),
            "language": language,
            "formats": formats,
        }

    def _real_extract(self, url):
        webpage = self._download_webpage(url)
        if is_series(url, webpage):
            pass  # current not working date January 31 2026 #TODO Fix when start working as normal
        else:
            return self.get_movie(webpage, url)
