import itertools
import re
from nobi_dl.utils import (
    _search_regex,
    _parse_a_tag,
    _parse_a_tags,
    fix_entries,
    _parse_resolution,
    _search_json,
    _og_thumbnail,
    _og_title,
    determine_ext,
    determine_filesize,
    is_series,
    random_id,
    check_both_host_are_same,
)
from nobi_dl import ExtractorBase


class VegaMoviesME(ExtractorBase):
    _IE_NAME = "vegamovies"
    _VALID_URL = r"https://?[^\.]+?\.?vegamovies[^/]+/[^?&]+"
    _SEARCH = True

    @property
    def HOST(self):
        return self.host_finder.vega_host()

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
                    "quality": _parse_resolution(title),
                    "source": "vegamovies",
                }
            )
        return results

    def _real_search(self, query, limit=50):
        results = []

        for pagenum in itertools.count(1):
            page = self._download_webpage(
                self.HOST,
                query={
                    "do": "search",
                    "subaction": "search",
                    "story": query,
                    "search_start": str(pagenum),
                },
                headers={
                    "referer": f"{self.HOST}/",
                },
            )
            results.extend(self._parse_content(page))
            next_page = _search_regex(r"<a[^>]+list_submit[^>]+>(\d+)<\/a>", page)
            if not next_page or len(results) >= limit:
                break

        return results

    def _parse_jekop_quailty(self, format, domain, headers, duration=None):
        file = format.get("file")
        title = format.get("title")
        if not file:
            return []
        file = file[1:] if file.startswith("~") else file
        file_url = f"{domain}/playlist/{file}.txt"
        file_data = self._download_webpage(file_url, headers=headers)
        if ".m3u8" not in file_data:
            return []
        return self.extract_m3u8_formats(
            file_data, title, headers=headers, duration=duration
        )

    def _extract_jekop_formats(self, webpage, duration=None):
        formats = []
        is_video_player = _search_regex(
            r"(?:playerconfigs|PlayerConfigs)\s*=\s*\{([\s\S]+?)}", webpage
        )
        if not is_video_player:
            self.to_screen("No Player for this movie")
            return []

        sid = _search_regex(r"""\bsrc\s*:\s*['\"]([^'\"]+)['\"]""", webpage)
        if not sid:
            self.to_screen("No Player formats for this movie")
            return []

        player_url = _search_regex(
            r"(https?:)?//[^\"'\s]+/player[^\"'\s]+", webpage, default=None
        )
        if not player_url:
            self.show_warning("Unable to find jekop player url")
            return []

        if player_url.startswith("//"):
            player_url = "https:" + player_url
        elif not player_url.startswith("http"):
            player_url = "https://" + player_url
        player_data = self._download_webpage(
            player_url, note="Downloading Jekop JS Player"
        )
        domain = _search_regex(r"""(https://?[^"']+)""", player_data)
        domain = f"https://{domain}" if "http" not in domain else domain
        video_url = f"{domain}/play/{sid}"
        video_webpage = self._download_webpage(
            video_url,
            headers={
                "Referer": "https://vegavinc.com/",
            },
            note="Downloading Jekop video webpage",
        )
        video_data = _search_json(r"=\s*(\{[\s\S]+?);", video_webpage)
        file_url = video_data.get("file")
        if not file_url:
            self.show_warning("Unable to Solve jekop data")
            return []
        common_headers = {
            "Referer": "https://vegavinc.com/",
            "X-CSRF-TOKEN": video_data.get("key"),
        }
        file_data = self._download_json(
            file_url,
            headers=common_headers,
            note="Downloading Multi Video Jekop information",
        )
        for file in file_data:
            formats.extend(
                self._parse_jekop_quailty(
                    file, domain, common_headers, duration=duration
                )
            )
        return formats

    def _get_movie(self, url_or_webpage):
        formats = []

        if isinstance(url_or_webpage, str) and "<" in url_or_webpage:
            webpage = url_or_webpage
        else:
            webpage = self._download_webpage(url_or_webpage)

        for h3 in re.findall(r"(<h3[\s\S]+?<\/h3>\s*(?:<h3[\s\S]+?<\/h3>)?)", webpage):
            if not any(k in h3 for k in ("nexdrive", "fast-dl", "st-dl", "extdrive")):
                continue
            h3_text = _search_regex(r"<h3[^>]+>(?:<[^>]+>)([^<]+)<", h3)
            for atag in _parse_a_tags(h3):
                href, name = _parse_a_tag(atag)
                if not href:
                    continue

                label = (name or "").lower()

                if not any(
                    k in label
                    for k in ("download", "to download", "click here to download")
                ):
                    continue

                formats.append(
                    {
                        "format_id": random_id(),
                        "url": href,
                        "acodec": True,
                        "vcodec": True,
                        "ext": determine_ext(href, href),
                        **determine_filesize(h3),
                        **_parse_resolution(h3_text),
                    }
                )

        if not formats:
            formats.extend(self._extract_jekop_formats(webpage))

        return {
            "title": _og_title(webpage),
            "thumbnail": _og_thumbnail(webpage),
            "formats": formats,
        }

    def extract_series_formats(self, url, op_webpage):
        webpage = self._download_webpage(url)
        title = _og_title(op_webpage)
        blocks = []
        for h4 in re.findall(r"<h4[\s\S]+?<\/h4>\s*<div[\s\S]+?<\/div>", webpage):
            h4_title = _search_regex(
                r"<h4[^>]+>\s*(?:<[^>]+>)?(?:<[^>]+>)?([^<]+)<", h4
            )
            h4_title = re.sub(r"(?:-:|:-)", "", h4_title)
            m = re.search(r"episodes?\s*[:\-]?\s*(\d+)", h4_title, re.I)
            ep_no = int(m.group(1))
            ep_key = f"EP {ep_no:02d}"
            season = _search_regex(r"(?is)(?:season|s0|s)\s*(\d+)", title, default=1)
            season
            for atag in _parse_a_tags(h4):
                href, name = _parse_a_tag(atag)
                label = (name or "").lower()
                if not any(k in label for k in ("g-direct", "direct")):
                    continue
                blocks.append(
                    {
                        "title": f"{title} - season {season} - {ep_key}",
                        "thumbanail": _og_thumbnail(op_webpage),
                        "episode": ep_no,
                        "season": season,
                        "formats": [
                            {
                                "format_id": random_id(),
                                "format_note": h4_title,
                                "url": href,
                                "acodec": True,
                                "vcodec": True,
                                "ext": "mkv",
                                **determine_filesize(name),
                                **_parse_resolution(webpage),
                            }
                        ],
                    }
                )

        return blocks

    def _get_series(self, url_or_name_or_webpage):
        if "<html" in url_or_name_or_webpage:
            webpage = url_or_name_or_webpage
        else:
            webpage = self._download_webpage(url_or_name_or_webpage)

        def entries(webpage):
            entries = []
            for atag in _parse_a_tags(webpage):
                href, name = _parse_a_tag(atag)
                format_id = (name or "").lower()
                if not any(
                    k in format_id
                    for k in (
                        "click here to download",
                        "to download",
                        "here to download",
                    )
                ):
                    continue
                entries.extend(self.extract_series_formats(href, webpage))
            return entries

        new_entires = fix_entries(self, entries(webpage))

        return self.playlist_result(
            entries=new_entires, playlist_title=_og_title(webpage)
        )

    def _url_fixer(self, url):
        host = self.host_finder.vega_host()
        check, new_url = check_both_host_are_same(url, host)
        if not check:
            return url
        self.show_warning("Domain is changed changing url to new domain")
        self.to_screen(f"Extracting from new url: {new_url}")
        return new_url

    def _real_extract(self, url):
        url = self._url_fixer(url)
        webpage = self._download_webpage(url)
        if is_series(url, webpage):
            return self._get_series(webpage)
        else:
            return self._get_movie(webpage)
