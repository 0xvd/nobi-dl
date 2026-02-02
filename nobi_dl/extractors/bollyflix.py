import itertools
import re
import urllib.parse

from nobi_dl import ExtractorBase
from nobi_dl.utils import (
    _og_thumbnail,
    _og_title,
    _parse_a_tag,
    _parse_a_tags,
    _parse_resolution,
    _search_regex,
    determine_ext,
    determine_filesize,
    fix_entries,
    is_series,
    random_id,
)

from ..downloader.fmt_resolver import Resolve_FMTS
from .hdhub import Hdhub4uME


class BollyFlixME(ExtractorBase):
    _IE_NAME = 'Bollyflix'
    _VALID_URL = r'^https?://.*bollyflix\..+'
    _SEARCH = True

    @property
    def HOST(self):
        return self.host_finder.bollyflix()

    @property
    def hdhub4u(self):
        return Hdhub4uME(self.md)

    @property
    def bolly_url_decoder(self):
        return Resolve_FMTS(self.md, None, None, None).bolly_url_decoder

    def _parse_content(self, html):
        results = []
        for article in re.findall(r'<article[\s\S]+?<\/article>', html):
            href = _search_regex(r'href="([^"]+)"', article)
            href = f'{self.HOST}{href}' if 'https' not in href else href
            thumbnail = _search_regex(r'src="([^"]+)"', article)
            thumbnail = (
                f'{self.HOST}{thumbnail}' if 'https' not in thumbnail else thumbnail
            )
            title = _search_regex(r'title="([^"]+)"', article)
            results.append(
                {
                    'title': title,
                    'thumbnail': thumbnail,
                    'url': href,
                    'acodec': True,
                    'vcodec': False,
                },
            )
        return results

    def _real_search(self, query):
        results = []
        for page in itertools.count(1):
            page = self._download_webpage(
                f'{self.HOST}/search/{urllib.parse.quote_plus(query)}/page/{page}',
                headers={
                    'referer': 'https://bollyflix.to/',
                },
            )
            results.extend(self._parse_content(page))
            next_page = _search_regex(r'<a[^>]+next[^>]+>Next<\/a>', page)
            if not next_page:
                break
        return results

    def get_movie(self, url_or_webpage):
        formats = []
        if '<html' in url_or_webpage:
            webpage = url_or_webpage
        else:
            webpage = self._download_webpage(url_or_webpage)
        for h5 in re.findall(r'<h5[\s\S]+?<\/h5>[\s\S]+?<a[\s\S]+?<\/a>', webpage):
            if '<a' not in h5:
                continue
            for atag in _parse_a_tags(h5):
                href, name = _parse_a_tag(atag)
                label = (name or '').lower()
                if not any(
                    k in label for k in ('google drive', 'le drive', 'ogle drive')
                ):
                    continue
                formats.append(
                    {
                        'format_id': random_id(),
                        'url': href,
                        'acodec': True,
                        'vcodec': True,
                        'ext': determine_ext(href, href),
                        **determine_filesize(h5),
                        **_parse_resolution(h5),
                    },
                )

        return {
            'title': _og_title(webpage),
            'thumbnail': _og_thumbnail(webpage),
            'formats': formats,
        }

    def block_parser(self, webpage, h4, url):
        entries = []

        fmt_url = self.bolly_url_decoder(url) if '?id=' in url else url
        fmt_webpage = self._download_webpage(fmt_url)
        for atag in _parse_a_tags(fmt_webpage):
            href, name = _parse_a_tag(atag)
            if not name:
                continue
            if not any(k in name.lower() for k in ('episode', 'epis')):
                continue
            ep_no = _search_regex(
                r'(?is)(?:episode|ep0|ep)\s*(\d+)', name, default=None,
            )
            season = _search_regex(
                r'(?is)(?:season|s|s0)\s*(\d+)', h4, default=None)
            entries.append(
                {
                    'title': f'{_og_title(webpage)} - Season {season} - Episode {ep_no}',
                    'season': season,
                    'episode': ep_no,
                    'formats': [
                        {
                            'url': href,
                            'format_id': random_id(),
                            'acodec': True,
                            'vcodec': False,
                            'ext': determine_ext(href, href),
                            **determine_filesize(h4),
                            **_parse_resolution(h4),
                        },
                    ],
                },
            )

        return entries

    def series_formats(self, webpage):
        entries = []
        for h4 in re.findall(r'<h4[\s\S]+?<\/h4>\s*<p[\s\S]+?<\/p>', webpage):
            if '<a' not in h4:
                continue
            for atag in _parse_a_tags(h4):
                href, name = _parse_a_tag(atag)
                if not any(
                    k in name.lower()
                    for k in (
                        'download links',
                        'download link',
                        'load links',
                        'load link',
                    )
                ):
                    continue
                if href is None:
                    continue
                entries.extend(self.block_parser(webpage, h4, href))

        return entries

    def _get_series(self, url_or_webpage, url):
        if '<html' in url_or_webpage:
            webpage = url_or_webpage
        else:
            webpage = self._download_webpage(url_or_webpage)

        entries = fix_entries(self, self.series_formats(webpage))

        return self.playlist_result(
            entries=entries,
            url=url,
            playlist_title=_og_title(webpage),
        )

    def _real_extract(self, url):
        webpage = self._download_webpage(url)
        if is_series(url, webpage):
            return self._get_series(webpage, url)
        else:
            return self.get_movie(webpage)
