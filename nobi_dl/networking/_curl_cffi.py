import curl_cffi
from curl_cffi import requests, const
from curl_cffi import exceptions as req_exc
from curl_cffi.requests.impersonate import BrowserTypeLiteral, DEFAULT_CHROME
from typing import get_args

SESSION = requests.Session()
DEFAULT_TIMEOUT = 20


class ImpersonateTargets:
    def __init__(self, logger):
        self.to_screen = logger.to_screen

    @staticmethod
    def _label(name: str, ver: str, only_client=False) -> str:
        if only_client is True:
            return name
        ver = (ver or "").strip().lstrip("_").replace("_", ".")
        return f"{name}-{ver}" if ver else name

    def _de_label(self, target):
        pass

    def _de_label(self, target: str | None) -> str | None:
        if not target:
            return None

        t = target.strip().lower()

        if ":" in t:
            t = t.split(":", 1)[0]

        t = t.replace(" ", "")
        t = t.replace("-ios", "_ios").replace("_ios", "_ios")
        t = t.replace("-android", "_android")
        t = t.replace("-beta", "_beta")

        if "-" in t:
            name, ver = t.split("-", 1)
        else:
            name, ver = t, ""

        if name == "safari":
            ver = ver.replace(".", "_")

        if name == "tor":
            ver = ver.replace(".", "")

        if name in {"chrome", "firefox", "edge"}:
            ver = ver.replace(".", "").replace("_", "")

        return f"{name}{ver}" if ver else name

    @property
    def all_targets(self):
        return list(get_args(BrowserTypeLiteral))

    def valid_targets(self):
        all_targets = self.all_targets
        filtered_targets = []
        for target in all_targets:
            client, _ = self._parse_target(target)
            if not client:
                continue
            filtered_targets.append(client)
        return filtered_targets

    def _parse_target(self, t: str, only_client=False) -> tuple[str, str]:
        if t.startswith("chrome"):
            ver = t.removeprefix("chrome")
            if t.endswith("_android"):
                return None, None
            return (self._label("Chrome", ver, only_client), "Macos-14")

        if t.startswith("firefox"):
            ver = t.removeprefix("firefox")
            return (self._label("Firefox", ver, only_client), "Macos-14")

        if t.startswith("safari"):
            ver = t.removeprefix("safari")
            if "ios" in t:
                ver = ver.replace("_ios", "")
                return (self._label("Safari", ver), "Ios-18.4")
            return (self._label("Safari", ver, only_client), "Macos-15")

        if t.startswith("edge"):
            ver = t.removeprefix("edge")
            return (self._label("Edge", ver, only_client), "Windows-10")

        if t.startswith("tor"):
            ver = t.removeprefix("tor")
            v = f"{ver[:2]}.{ver[2:]}" if ver.isdigit() and len(ver) == 3 else ver
            return (self._label("Tor", v, only_client), "Macos-14")

    def show_impersonate_table(self) -> int:
        rows = []
        for t in self.all_targets:
            client, os = self._parse_target(t)
            if not client:
                continue
            rows.append((client, os, "curl_cffi"))

        rows.sort(key=lambda r: (r[0].split("-")[0], r[0]))

        self.to_screen("[info] Available impersonate targets")
        self.to_screen(f"{'Client':<12}  {'OS':<12}  {'Source'}")
        self.to_screen("-" * 36)
        for client, os, src in rows:
            self.to_screen(f"{client:<12}  {os:<12}  {src}")
        return 0


class Curl_cfiiRH:
    def __init__(
        self,
        url,
        method="GET",
        impersonate=None,
        headers=None,
        cookies=None,
        query=None,
        data=None,
        timeout=DEFAULT_TIMEOUT,
        retries=2,
        verbose=False,
        logger=None,
        stream=False,
    ):
        self.logger = logger
        self.verbose = verbose
        self.url = url
        self.method = method
        self.impersonate = impersonate
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.query = query or {}
        self.data = data or {}
        self.timeout = timeout
        self.retries = retries
        self.stream = stream

    def __call__(self):
        return self._request()

    def _print_verbose(self, msg):
        if self.verbose is True:
            return self.logger.to_stdout(msg)

    def print_traffic(self) -> dict:
        if not self.verbose:
            return {}
        self.logger.to_stdout(f"[info] Sending Request via {curl_cffi.__name__}")

        return {const.CurlOpt.VERBOSE: 1}

    def _request(self):
        from ._request_handler import std_headers

        default_headers = dict(std_headers)
        default_headers.update(self.headers)
        curl_opts = self.print_traffic()
        if curl_opts:
            SESSION.curl_options = curl_opts

        if self.impersonate is None:
            self.impersonate = DEFAULT_CHROME

        last_err = None
        for _ in range(self.retries + 1):
            try:
                resp = SESSION.request(
                    self.method,
                    self.url,
                    cookies=self.cookies,
                    params=self.query,
                    data=self.data,
                    timeout=self.timeout,
                    headers=default_headers,
                    impersonate=self.impersonate,
                    stream=self.stream,
                )

                SESSION.cookies.update(resp.cookies)
                if resp.status_code in (429, 503, 502, 504):
                    last_err = RuntimeError(f"HTTP {resp.status_code}")
                    continue

                return resp

            except req_exc.Timeout as e:
                last_err = e
                continue

        raise last_err
