import re
from .networking import Request
import urllib.parse
from .utils import (
    approx_filesize_from_tbr,
    _parse_m3u8_resolution,
    _m3u8_attr,
    random_id,
)


class ExtractorBase:
    _EXTRACTOR_CLASSES = None
    _IE_NAME = None
    _VALID_URL = None

    def __init__(self, md=None):
        from .host_finder import HOST_FINDER

        self.md = md
        self.impersonate = md.impersonate
        self.to_screen = md.to_screen
        self.write_debug = md.write_debug
        self.raise_error = md.raise_error
        self.show_warning = md.show_warning
        self.logger = md.logger
        self.network_verbose = md.opts.print_traffic
        self.write = self.logger.to_stdout
        self.host_finder = HOST_FINDER(md, self)

    @classmethod
    def suitable(cls, url: str) -> bool:
        return bool(cls._VALID_URL and re.match(cls._VALID_URL, url))

    def extract(self, url: str) -> dict:
        return self._real_extract(url)

    def _real_extract(self, url: str) -> dict:
        raise NotImplementedError

    @classmethod
    def import_extractors(cls):
        if cls._EXTRACTOR_CLASSES is not None:
            return
        from .extractors import extractors as ex

        cls._EXTRACTOR_CLASSES = ex.ALL

    @classmethod
    def gen_extractors(cls, md):
        cls.import_extractors()
        return [ie_cls(md) for ie_cls in cls._EXTRACTOR_CLASSES]

    @classmethod
    def get_extractor(cls, md, url: str):
        for ie in cls.gen_extractors(md):
            if ie.suitable(url):
                return ie
        return None

    def _request(
        self,
        url,
        *,
        method="GET",
        headers=None,
        cookies=None,
        query=None,
        data=None,
        timeout=20,
        note=None,
    ):
        if note:
            self.to_screen(note)

        kw = dict(
            url=url,
            method=method,
            headers=headers,
            cookies=cookies,
            query=query,
            data=data,
            timeout=timeout,
            impersonate=self.impersonate,
        )

        return Request(**kw, verbose=self.network_verbose, logger=self.logger)()

    def _download_webpage(self, url, note="Downloading Webpage", **kw):
        return self._request(url, method="GET", **kw, note=note).text

    def _download_json(self, url, note="Downloading Json", **kw):
        method = "POST" if (kw.get("data") or {}) else "GET"
        return self._request(url, method=method, **kw, note=note).json()

    def _ping_host(self, url, note="ping Host", **kw):
        return self._request(url, method="GET", **kw, note=note).status_code

    def extract_m3u8_formats(self, m3u8_url, label="hls", headers=None, duration=None):
        m3u8 = self._download_webpage(
            m3u8_url, headers=headers or {}, note="Downloading m3u8 information"
        )
        if not m3u8 or not m3u8.lstrip().startswith("#EXTM3U"):
            return []

        if "#EXT-X-STREAM-INF" not in m3u8:
            fmt = [
                {
                    "url": m3u8_url,
                    "label": random_id(),
                    "ext": "mp4",
                    "vcodec": True,
                    "acodec": True,
                }
            ]
            if headers:
                fmt["http_headers"] = headers

            return fmt

        out = []
        last = None
        for line in m3u8.splitlines():
            line = line.strip()
            if line.startswith("#EXT-X-STREAM-INF:"):
                last = line
                continue
            if not line or line.startswith("#") or not last:
                continue

            u = urllib.parse.urljoin(m3u8_url, line)
            w, h = _parse_m3u8_resolution(last)
            bw = _m3u8_attr(last, "BANDWIDTH")
            tbr = int(bw) // 1000 if (bw and bw.isdigit()) else None

            fmt = {
                "url": u,
                "format_id": (f"{h or w or 'var'}"),
                "width": w,
                "height": h,
                "tbr": tbr,
                "ext": "mp4",
                "vcodec": True,
                "acodec": True,
                "format_note": label,
            }
            if headers:
                fmt["http_headers"] = headers
            if duration:
                approx = approx_filesize_from_tbr(tbr, duration)
                if approx:
                    fmt["filesize_approx"] = approx
            out.append(fmt)
            last = None

        return out

    def playlist_result(
        self,
        entries,
        playlist_url=None,
        playlist_title=None,
        playlist_description=None,
        **kwargs,
    ):
        if playlist_url:
            kwargs["url"] = playlist_url
        if playlist_title:
            kwargs["title"] = playlist_title
        if playlist_description is not None:
            kwargs["description"] = playlist_description
        return {
            **kwargs,
            "_type": "series",
            "entries": entries,
        }
