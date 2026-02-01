from .logger import Log
from nobi_dl.options import options
from .version import __version__
import sys
import platform
import ssl
import struct
from .common import ExtractorBase
from nobi_dl.format_render import render_formats_table
import json
import time
from .downloader import Downloader, Resolve_FMTS
from .search import Searcher
from .utils import (
    NobiDLError,
    ascii_color,
)


class NobiDL:
    def __init__(self, opts, args, opt_error):
        self.args = args
        self.opts = opts
        self.impersonate = getattr(opts, "impersonate", None)
        self.logger = Log(opts)
        self.write_debug = self.logger.write_debug
        self.to_screen = self.logger.to_screen
        self.raise_error = self.logger.error
        self.show_warning = self.logger.warning
        self.write = self.logger.to_stdout
        self.list_impersonate = self.opts.list_impersonate
        self.dump_json = self.opts.dump_json
        self.downloader = Downloader
        self.verbose = self.opts.verbose
        self.extractor_base = ExtractorBase(self)
        self.opt_error = opt_error
        self.list_extractors = self.opts.list_extractors
        self.force_extractor = self.opts.force_extractor
        self.searcher = Searcher(self, self.force_extractor)

    def _real_initialize(self):
        if self.list_impersonate is True:
            return 0
        argv = sys.argv[1:]
        pyver = sys.version.split()[0]
        impl = platform.python_implementation()
        arch = "x86_64" if struct.calcsize("P") * 8 == 64 else "x86"
        plat = platform.platform()
        openssl = getattr(ssl, "OPENSSL_VERSION", "unknown")
        ies = ExtractorBase.gen_extractors(self)
        request_handlers = ", ".join(self.request_handlers())
        self.write_debug(f"Command-line config: {argv}")
        self.write_debug(f"nobi-dl version: {__version__}")
        self.write_debug(f"Python {pyver} ({impl} {arch}) - {plat} ({openssl})")
        self.write_debug(f"exe: {sys.executable}")
        self.write_debug(f"Request Handlers : {request_handlers}")
        self.write_debug(f"Loaded {len(ies)} extractors")
        self.ping_and_speed()

    def _fmt_speed(self, bps: float) -> str:
        for unit in ("B/s", "KiB/s", "MiB/s", "GiB/s"):
            if bps < 1024:
                return f"{bps:.2f} {unit}"
            bps /= 1024
        return f"{bps:.2f} TiB/s"

    def estimate_speed(self):
        try:
            url = "https://speed.cloudflare.com/__down?bytes=5000000"
            t0 = time.perf_counter()
            r = self.extractor_base._request(url)
            size = len(r.content)
            dt = time.perf_counter() - t0
            bps = size / max(dt, 1e-6)
            speed_str = self._fmt_speed(bps)
            self.write_debug(f"Downloading Speed: {speed_str}")
        except Exception as e:
            self.write_debug(f"Downloading Speed test fail {e}")

    def ping_and_speed(self):
        if not self.verbose:
            return
        if self.verbose < 2:
            return

        url = "https://www.google.com/generate_204"
        try:
            t0 = time.perf_counter()
            self.extractor_base._request(url)
            ping_ms = (time.perf_counter() - t0) * 1000
            self.write_debug(f"Ping: {ping_ms:.1f} ms")
            self.estimate_speed()
        except Exception as e:
            self.write_debug(f"Ping fail {e}")

    def show_list_extractors(self):
        if self.list_extractors is False:
            return
        for extractor in self.extractor_base.gen_extractors(self):
            extractor = extractor._IE_NAME or extractor.__name__
            self.write(f"{extractor}")

        return 0

    def list_impersonate_targets(self):
        try:
            from .networking._curl_cffi import ImpersonateTargets

            if not self.list_impersonate:
                return
            ImpersonateTargets(self.logger).show_impersonate_table()
        except ImportError:
            raise NobiDLError(
                'Curl_cffi not installed please install curl_cffi - command "pip install curl_cffi"',
                expected=True,
            )
        return 0

    def request_handlers(self):
        request_handlers = set()
        try:
            import requests

            request_handlers.add(requests.__name__.capitalize())
        except Exception:
            pass

        try:
            import curl_cffi

            request_handlers.add(curl_cffi.__name__.capitalize())
        except Exception:
            pass

        try:
            import urllib

            request_handlers.add(urllib.__name__.capitalize())
        except Exception:
            pass

        return request_handlers

    def resolve_info_dict(self, info_dict_or_entry):
        formats = info_dict_or_entry.get("formats")
        resolved_formats = Resolve_FMTS(self, None, formats)()
        info_dict_or_entry.pop("formats")
        return {**info_dict_or_entry, "formats": resolved_formats}

    def handle_playlist(self, info_dict):
        resolved_entries = []
        entries = info_dict.get("entries", [])

        items = len(entries)
        title = info_dict.get("title")

        self.write(f"[info] Downloading Series: {title}")
        self.to_screen(f"Playlist {title} Downloading {items} items of {items}")

        for item, entry in enumerate(entries, start=1):
            self.to_screen(
                f"Downloading item {ascii_color(item, 32)} of {ascii_color(items, 34)}"
            )

            if self.opts.dump_json:
                resolved_entry = self.resolve_info_dict(entry)
                resolved_entries.append(resolved_entry)
                self.write(json.dumps(resolved_entry))
                continue

            self.downloader(self, entry, self.opts, self.logger)()

        if self.opts.dump_json:
            playlist = {
                **info_dict,
                "entries": resolved_entries,
            }
            self.write(json.dumps(playlist))

        return playlist if playlist else None

    def gen_info_dict(self, info):
        info.setdefault("fulltitle", info.get("title"))
        info.setdefault("thumbnails", [])
        info.setdefault("series", bool(info.get("entries")))
        info.setdefault("formats", [])

        for f in info["formats"]:
            f.setdefault("protocol", "https")
            f.setdefault("vcodec", None)
            f.setdefault("acodec", None)
            f.setdefault("fps", None)
            f.setdefault("filesize", None)
            f.setdefault("filesize_approx", None)
            f.setdefault("abr", None)
            f.setdefault("tbr", None)
            f.setdefault("language", None)
            f.setdefault("audio_channels", None)
            headers = f.get("http_headers") or f.get("https_headers")
            if headers:
                f.setdefault("http_headers", headers)

        return info

    def _real_extract(self, url=None):
        if self.list_impersonate:
            return self.list_impersonate_targets()

        if self.list_extractors:
            return self.show_list_extractors()

        if not self.opts.search and not self.args:
            self.opt_error("No url or search query provided")
            return

        url = None
        q = None

        if self.opts.search:
            q = self.opts.search

        elif self.args:
            arg = self.args[0]
            if arg.startswith(("http://", "https://")):
                url = arg
            else:
                q = arg

        if q:
            result = self.searcher.search(q)
            best = result.get("best")
            if not best:
                self.to_screen(f"[info] No Result found for {q}")
                return
            url = best.get("url")

        if not url:
            self.to_screen("[error] No URL provided")
            return

        ie = ExtractorBase.get_extractor(self, url)
        if not ie:
            self.raise_error(f"Unsupported url: {url}")
            return

        self.logger.set_ie(ie)
        self.to_screen(f"Extracting url: {url}")
        info = ie.extract(url)
        if not info or info is None:
            return self.show_warning(
                "Extractor return nothing there is an error in Extractor."
            )
        info_dict = self.gen_info_dict(info)
        if info_dict.get("_type") == "series":
            return self.handle_playlist(info)

        if not info_dict.get("formats"):
            raise NobiDLError("No Formats Found", url=url)

        if self.opts.list_formats and info_dict.get("formats"):
            title = info_dict.get("title")
            self.write(f"[info] Available formats for {title}")
            self.write(render_formats_table(info_dict["formats"], info_dict))
            pass

        if self.opts.dump_json:
            resolved_info = self.resolve_info_dict(info_dict)
            self.write(json.dumps(resolved_info))
            pass

        if not self.opts.list_formats and info_dict.get("formats"):
            self.downloader(self, info_dict, self.opts, self.logger)()
            return

        return info_dict


def main():
    opts, args, opt_error = options()
    md = NobiDL(opts, args, opt_error)
    ExtractorBase(md)
    try:
        md._real_initialize()
        md._real_extract()

    except KeyboardInterrupt:
        md.write("Interrupted by user")
        raise SystemExit(130)

    except NobiDLError as e:
        if opts.verbose:
            raise e
        md.write(e)
