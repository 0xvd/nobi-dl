from .http import HttpDownloader
from .hls import HlsDL
from .common import BestFMT
from .fmt_resolver import Resolve_FMTS


class Downloader:
    def __init__(self, md, info_dict, options, logger):
        self.info_dict = info_dict
        self.logger = logger
        self.options = options
        self.md = md

    def __call__(self):
        return self.downloader()

    def downloader(self):
        formats = self.info_dict.get("formats") or []
        bfmt = BestFMT(formats)()
        bfmt = Resolve_FMTS(self.md, bfmt, None)()
        url = bfmt.get("url")
        if "m3u8" in url:
            return HlsDL(bfmt, self.info_dict, self.options, self.logger)()
        else:
            return HttpDownloader(bfmt, self.info_dict, self.options, self.logger)()
