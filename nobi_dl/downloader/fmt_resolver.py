from ..nobi_dl import ExtractorBase
from ..utils import (
    _search_regex,
    _get_qparam,
    _parse_resolution,
    determine_ext,
    determine_filesize,
    _og_title,
    url_filename,
    random_id,
    _parse_a_tag,
    _parse_a_tags,
    clean_url,
)
import re
from ..extractors.hdhub import Hdhub4uME


class Resolve_FMTS(ExtractorBase):
    def __init__(self, md, fmt: str = None, formats: dict = None):
        super().__init__(md)
        self.formats = formats
        self.fmt = fmt

    _GLOBAL_SEEN_URLS = set()

    @property
    def hdhubme(self):
        return Hdhub4uME(self.md)

    def noter(self, msg):
        return f"[lazy resolver] {msg}"

    def _google_resolver(self, url, need_dict=False):
        if "google" not in url:
            response = self._request(url, method="HEAD")
            url = _search_regex(
                r"""(?:href[^'"]+["'])?(https://?[^/]+googleuser[^"'?#]+)(?:['"])?""",
                response.url,
            )
            if "google" not in url:
                return {} if need_dict is True else None
        google_head = self._request(
            url, method="HEAD", note=self.noter("Ping Google server")
        )
        if google_head.status_code != 200:
            return {}
        headers = google_head.headers
        cd = headers.get("Content-Disposition", "")
        filename = _search_regex(r'filename\s*=\s*"([^"]+)"', cd)
        data = {
            "url": url,
            "ext": determine_ext(url, filename),
            "acodec": True,
            "vcodec": True,
            "format_id": random_id(),
            **_parse_resolution(filename),
            **determine_filesize(headers),
        }
        if need_dict is True:
            return [data]
        return data

    def fast_dl(self, url):
        fast_data = self._request(
            url, method="POST", note=self.noter("Downloading Fast DL data")
        ).text
        google_url = _search_regex(
            r"""href[^'"]+["'](https://?[^/]+googleuser[^"']+)['"]""", fast_data
        )
        if not google_url:
            return None
        return self._google_resolver(google_url, True)

    def _parse_pixel(self, url, format_id=None):
        API = "{}/api/file/{}?download"
        if "pixel" not in url:
            return []
        self._GLOBAL_SEEN_URLS.add(url)

        if "?id=" in url:
            req = self._request(
                url, method="HEAD", note=self.noter("ping pixel server")
            )
            google_url = _get_qparam(req.url, ("url", "url"))
            if not google_url:
                return []
            return [self._google_resolver(google_url, need_dict=True)]
        elif "?id" not in url:
            webpage = self._download_webpage(
                url, note="Downloading pixel server information"
            )
            d_vid = re.search(
                r"(https?://)?(?P<domain>[^/]+)/.+/(?P<vid>[^/?&#]+)", url
            )
            if not d_vid:
                return []
            title = _og_title(webpage)
            domain, vid = d_vid.group("domain", "vid")
            host = f"https://{domain}" if "http" not in domain else domain
            url = API.format(host, vid)

            return [
                {
                    "url": url,
                    "format_id": format_id or title,
                    **_parse_resolution(title),
                    "acodec": True,
                    "vcodec": True,
                    "ext": determine_ext(url),
                    **determine_filesize(webpage),
                }
            ]

        return []

    def _parse_fsl(self, url: str, format_id: str | None = None):
        req = self._request(url, method="HEAD", note="ping FSL server")
        if getattr(req, "status_code", 0) != 200:
            return []
        real_url = getattr(req, "url", url) or url
        if "google" in real_url:
            return [self._google_resolver(real_url, True)]
        headers = req.headers
        cd = (
            headers.get("Content-Disposition")
            or headers.get("content-disposition")
            or ""
        )
        filename = None
        try:
            filename = _search_regex(
                r'filename\*\s*=\s*[^\'"]*\'\'([^;]+)|filename\s*=\s*"([^"]+)"', cd
            )
            if isinstance(filename, (list, tuple)):
                filename = next((x for x in filename if x), None)
        except Exception:
            filename = None
        filename = filename or url_filename(real_url) or url_filename(url) or "download"
        out_format_id = (format_id or filename or "download").strip()
        return [
            {
                "url": real_url,
                "format_id": out_format_id,
                **_parse_resolution(filename),
                "acodec": True,
                "vcodec": True,
                "ext": determine_ext(real_url),
                **determine_filesize(headers),
            }
        ]

    def _parse_direct_drive(self, url):
        formats = []
        domain = _search_regex(
            r'(https?://[^"\s<>]*drive[^"/\s<>]*)', url, default=None
        )
        if not domain:
            return []

        webpage = self._download_webpage(
            url, note=self.noter("Downloading hubdrive webpage")
        )

        did = None
        if not did:
            did = _search_regex(
                r'\bid\s*=\s*["\']down-id["\'][^>]*>\s*([^<\s]+)', webpage, default=None
            )
        if not did:
            did = _search_regex(r"\bdown-id[^>]*>\s*([^<\s]+)", webpage, default=None)

        if not did:
            return []

        data = self._download_json(
            f"{domain}/ajax.php?ajax=direct-download",
            data={"id": str(did)},
            headers={
                "Origin": domain,
                "Referer": f"{domain}/",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=30,
        )

        if str(data.get("code")) != "200":
            self.to_screen("retrying for extracting hubdrive information")
            data = self._download_json(
                f"{domain}/ajax.php?ajax=direct-download",
                data={"id": str(did)},
                headers={
                    "Origin": domain,
                    "Referer": f"{domain}/",
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=30,
            )

        if str(data.get("code")) != "200":
            return []

        d_data = data.get("data") or {}
        format_id = d_data.get("n") or ""

        gd_url = d_data.get("gd")
        file_path = data.get("file")
        if gd_url:
            formats.append(self._google_resolver(gd_url, True))

        if file_path:
            dl_url = (
                file_path if file_path.startswith("http") else f"{domain}{file_path}"
            )
            worker_webpage = self._download_webpage(
                dl_url, "Downloading hubdrive worker webpage"
            )
            direct_url = _search_regex(
                r'(https?://[^"\s<>]*workers\.dev/[^"\s<>]+)',
                worker_webpage,
                default=None,
            )
            if direct_url:
                h = self._request(direct_url, method="HEAD")
                real = getattr(h, "url", direct_url) or direct_url
                formats.append(
                    {
                        "format_id": format_id,
                        "url": real,
                        **_parse_resolution(format_id or worker_webpage),
                        "acodec": True,
                        "vcodec": True,
                        "ext": determine_ext(real),
                        **determine_filesize(h.headers),
                    }
                )

        return formats

    def _tech_unblock_decoder(self, url):
        if "tech" not in url:
            return None
        domain, value = re.search(
            r"https://?(?P<domain>[^/]+)[^\bid]+id\s*=\s*(?P<token>[^?&#]+)", url
        ).groups()
        domain = f"https://{domain}" if "://" not in domain else domain
        req = self._request(
            domain,
            data={"_wp_http": value},
            method="POST",
            note=self.noter("Downloading tech unblock webpage"),
        )
        url, name, post_value = re.search(
            r'''<form[^>]+action\s*=\s*['\"](?P<url>[^'\"]+)"?[^>]+>[^>]+name\s*=\s*['\"]+(?P<name>[^'\"]+)"[^>]+value\s*=\s*['\"]+(?P<value>[^'\"]+)"''',
            req.text,
        ).groups()
        req2 = self._request(
            url,
            data={name: post_value},
            method="POST",
            note=self.noter("Redirecting from tech unblock"),
        )
        url, cname, cvalue = re.search(
            r"""setAttribute.+\b(?P<url>https[^'\"]+)[\s\S]+?s[^'\"]+'(?P<cname>[^'\"]+)'[^'\"]+'(?P<cvalue>[^'\"]+)""",
            req2.text,
        ).groups()
        req3 = self._request(
            url,
            cookies={cname: cvalue},
            method="POST",
            note=self.noter("Downloading Final webpage of tech unblock"),
        )
        final_url = re.search(r'''url\s*=\s*(?:['\"]+)?([^'\"]+)?"''', req3.text).group(
            1
        )
        return final_url if final_url else None

    def modpro(self, url):
        webpage = self._download_webpage(url)
        for atag in _parse_a_tags(webpage):
            href, name = _parse_a_tag(atag)
            label = (name or "").lower()
            if not any(
                k in label
                for k in ("fast server", "st serve", "google drive", "gle drive")
            ):
                continue
            if "fast" in label:
                return self._tech_unblock_decoder(href) if "tech" in href else href
            elif "lr drive" in label:
                return self._tech_unblock_decoder(href) if "tech" in href else href
            else:
                return href
        return None

    def _parse_hubcloud(self, url):
        if not any(k in url for k in ("hub", "cloud", "id=")):
            return []
        if "?id" in url:
            url = self.hdhubme._hdhub_url_decoder(url)
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

            if "pixel" in check:
                return self._parse_pixel(href)
            elif "fsl" in check:
                return self._parse_fsl(href)
        return formats

    def drive_seed(self, url):
        if "modpro" in url or "archives" in url:
            url = self.modpro(url)
        elif "tech" in url:
            url = self._tech_unblock_decoder(url)
        elif "driveseed" in url:
            url = url
        domain = clean_url(url)
        webpage = self._download_webpage(url, note="Downloading drive seed webpage")
        if "/file" not in url:
            path = _search_regex(r"""['\"]+((?:https://)?/?fil[^'\"]+)""", webpage)
            url = f"{domain}{path}" if "http" not in path else path
            webpage = self._download_webpage(
                url, note="Downloading drive seed Redirected webpage"
            )

        for atag in _parse_a_tags(webpage):
            href, name = _parse_a_tag(atag)
            label = (name or "").lower()
            if not any(k in label for k in ("instant download", "direct links")):
                continue
            if "instant" in label:
                return self._google_resolver(href)
            elif "driveseed" in href:
                return self.driveseed_direct(href)
            else:
                return href

    def driveseed_direct(self, url):
        formats = []
        if "drive" not in url:
            return None
        url = f"{url}?type=1" if "type=1" not in url else url
        webpage = self._download_webpage(url).text
        if "available for this file" in webpage.lower():
            webpage = self._download_webpage(url.replace("type=1", "type=2"))
        for atag in _parse_a_tags(webpage):
            href, name = _parse_a_tag(atag)
            label = (name or "").lower()
            if "download" not in label:
                continue
            if "dev" not in href:
                continue
            formats.append(
                {
                    "format_id": random_id(),
                    "url": href,
                    "acodec": True,
                    "vcodec": True,
                    "ext": determine_ext(href, href),
                    **determine_filesize(webpage),
                    **_parse_resolution(webpage),
                }
            )

    def nextdrive(self, url):
        webpage = self._download_webpage(url, "Downloading NextGen Webpage")
        for atag in _parse_a_tags(webpage):
            href, _ = _parse_a_tag(atag)
            if not href:
                continue
            if not any(k in href for k in ("fast-dl", "fast-d", "st-dl")):
                continue
            return self.fast_dl(href)

        return []

    def resolve_provider(self, url):
        if "pixel" in url:
            return self.pixel_cdn(url)
        elif "fsl" in url:
            return self._parse_fsl(url)
        elif any(k in url for k in ("nextdrive", "extdrive", "exdrive")):
            return self.nextdrive(url)
        elif any(k in url for k in ("hubcloud", "web", "?id=")):
            return self._parse_hubcloud(url)
        elif any(k in url for k in ("driveseed", "tech", "modpro")):
            return self.drive_seed(url)
        elif "hubdrive" in url:
            return self._parse_direct_drive(url)
        elif "fast" in url:
            return self.fast_dl(url)
        return url

    def resolve_format(self, fmt: dict) -> list[dict]:
        url = fmt.get("url")
        if not url:
            return []

        if "m3u8" in url:
            return [fmt]

        fmts = self.resolve_provider(url)

        if not fmts:
            return []

        if isinstance(fmts, list):
            return fmts

        if isinstance(fmts, dict):
            return [fmts]

        return [fmt]

    def __call__(self):
        return self._real_solver()

    def _real_solver(self) -> list[dict]:
        self.write_debug("Lazy formats Resolving")

        if self.formats:
            resolved_formats = []
            for fmt in self.formats:
                fmt = self.resolve_format(fmt)
                resolved_formats.extend(fmt)
            return resolved_formats

        normal_dict_fmt = self.resolve_format(self.fmt)
        return (
            normal_dict_fmt[0]
            if isinstance(normal_dict_fmt, list) and self.fmt
            else normal_dict_fmt
        )
