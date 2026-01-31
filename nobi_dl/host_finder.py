import json
import time
import tempfile
from pathlib import Path
from .utils import clean_url, _search_regex, b64d

CACHE_FILE = Path(tempfile.gettempdir()) / "movie_dl_cache.json"
TTL_SECONDS = 24 * 60 * 60


class HOST_FINDER:
    def __init__(self, md, extractor):
        self.md = md
        self.extractor = extractor
        self.impersonate = md.impersonate
        self.to_screen = md.to_screen
        self.write_debug = md.write_debug
        self.raise_error = md.raise_error
        self.show_warning = md.show_warning
        self.logger = md.logger
        self.network_verbose = md.opts.print_traffic
        self.write = self.logger.to_stdout
        self._request = extractor._request
        self._download_webpage = extractor._download_webpage
        self._download_json = extractor._download_json

    DEFAULT_HOSTS = {
        "vega": "https://vegamovies.compare",
        "hdhub": "https://new3.hdhub4u.fo",
        "bollyflix": "https://bollyflix.do",
        "4khub": "https://4khdhub.dad",
        "moviesmod": "https://moviesmod.town",
    }

    def _read_cache(self) -> dict:
        if not CACHE_FILE.exists():
            return {}
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def _write_cache(self, data: dict):
        CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _get_cached_host(self, name: str, no_ttl_check=False) -> str | None:
        cache = self._read_cache()
        item = cache.get(name) or {}
        host = item.get("host")
        if no_ttl_check is True:
            return host
        exp = item.get("expires_at", 0)
        if isinstance(host, str) and host and exp > time.time():
            return host
        return None

    def _set_cached_host(self, name: str, host: str):
        cache = self._read_cache()
        cache[name] = {"host": host, "expires_at": time.time() + TTL_SECONDS}
        self._write_cache(cache)

    def _resolve_and_cache(self, name: str, resolver):
        host = self._get_cached_host(name)
        if host:
            return host
        host = resolver()
        if isinstance(host, str) and host:
            self._set_cached_host(name, host)
            return host
        return None

    def _resolve_vega(self) -> str | None:
        old_domain = self._get_cached_host("vega", True)
        if not old_domain:
            old_domain = self.DEFAULT_HOSTS.get("vega")
        try:
            req = self._request(old_domain)
            code = getattr(req, "status_code", None)
            final_url = getattr(req, "url", None)
            if code in (301, 302) and final_url:
                return clean_url(final_url)
        except Exception:
            return self.DEFAULT_HOSTS.get("vega")
        return old_domain

    def _resolve_hdhub(self) -> str | None:
        data = self._download_json(
            "https://cdn.hub4u.cloud/host/?v=2026011617",
            headers={"referer": "https://hdhub4u.gd/", "origin": "https://hdhub4u.gd"},
        )
        c = (data or {}).get("c")
        return clean_url(b64d(c)) if c else None

    def _resolve_4khub(self) -> str | None:
        hh = self.hdhub_host()
        if not hh:
            return None
        webpage = self._download_webpage(hh)
        return _search_regex(r'((?:https://)?4khd[^"]+)', webpage)

    def _resolve_bollyflix(self) -> str | None:
        old_domain = self._get_cached_host("bollyflix", True)
        if not old_domain:
            old_domain = self.DEFAULT_HOSTS.get("bollyflix")
        try:
            req = self._request(old_domain)
            code = getattr(req, "status_code", None)
            final_url = getattr(req, "url", None)
            if code in (301, 302, 303, 307, 308) and final_url:
                return clean_url(final_url)
        except Exception:
            return self.DEFAULT_HOSTS.get("bollyflix")
        return old_domain

    def _resolve_moviemod(self) -> str | None:
        old_domain = self._get_cached_host("moviesmod", True)
        if not old_domain:
            old_domain = self.DEFAULT_HOSTS.get("moviesmod")
        try:
            req = self._request(old_domain)
            code = getattr(req, "status_code", None)
            final_url = getattr(req, "url", None)
            if code in (301, 302, 303, 307, 308) and final_url:
                return clean_url(final_url)
        except Exception:
            return self.DEFAULT_HOSTS.get("moviesmod")
        return old_domain

    def vega_host(self) -> str | None:
        return self._resolve_and_cache("vega", self._resolve_vega)

    def hdhub_host(self) -> str | None:
        return self._resolve_and_cache("hdhub", self._resolve_hdhub)

    def _4k_host(self) -> str | None:
        return self._resolve_and_cache("4khub", self._resolve_4khub)

    def bollyflix(self) -> str | None:
        return self._resolve_and_cache("bollyflix", self._resolve_bollyflix)

    def moviemod(self) -> str | None:
        return self._resolve_and_cache("moviesmod", self._resolve_moviemod)

    def _hdhub_search_host(self) -> str | None:
        host = self.hdhub_host()
        if not host:
            return None
        webpage = self._download_webpage(f"{host}/search.html")
        search_host = _search_regex(r'https?://(search[^/]+)/[^",]+', webpage)
        if not search_host:
            return None
        return clean_url(search_host)
