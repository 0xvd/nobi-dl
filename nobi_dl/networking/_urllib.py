import json
import urllib.request
import urllib.parse
import urllib.error
import socket
import http.client


class HttpResponse:
    def __init__(self, resp, body: bytes):
        self._resp = resp
        self._body = body
        self._headers = dict(resp.headers)

    @property
    def content(self):
        return self._body

    @property
    def text(self):
        return self._body.decode("utf-8", errors="ignore")

    def json(self):
        return json.loads(self.text)
    
    def iter_content(self, chunk_size=8192):
        if self._body:
            for i in range(0, len(self._body), chunk_size):
                yield self._body[i:i + chunk_size]
            return

        while True:
            chunk = self._resp.read(chunk_size)
            if not chunk:
                break
            yield chunk

    @property
    def url(self):
        return getattr(self._resp, "url", None)

    @property
    def status_code(self):
        return getattr(self._resp, "status", None) or self._resp.getcode()

    @property
    def headers(self):
        return self._headers


class UrllibRH:
    def __init__(
        self,
        url,
        headers=None,
        cookies=None,
        query=None,
        data=None,
        timeout=20,
        method="GET",
        retries=2,
        verbose=False,
        logger=None,
        stream=False,
    ):
        self.logger = logger
        self.verbose = verbose
        self.url = url
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.query = query or {}
        self.data = data
        self.timeout = timeout or 20
        self.method = (method or "GET").upper()
        self.retries = retries
        self.stream = stream

    def __call__(self):
        return self._request()

    def _print_verbose(self, msg):
        if self.verbose and self.logger:
            self.logger.to_stdout(msg)

    def print_traffic(self):
        if not self.verbose:
            return
        self._print_verbose("[info] Sending Request via urllib")
        http.client.HTTPSConnection.debuglevel = 1
        http.client.HTTPConnection.debuglevel = 1

    def _build_url(self) -> str:
        if not self.query:
            return self.url
        parts = list(urllib.parse.urlsplit(self.url))
        q = dict(urllib.parse.parse_qsl(parts[3], keep_blank_values=True))
        q.update(self.query)
        parts[3] = urllib.parse.urlencode(q, doseq=True)
        return urllib.parse.urlunsplit(parts)

    @property
    def update_cookies_in_headers(self):
        if not self.cookies:
            return {}

        if isinstance(self.cookies, dict):
            cookie_header = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        else:
            cookie_header = str(self.cookies)

        return {
            "Cookie": cookie_header
        }

    def _request(self):
        from ._request_handler import std_headers

        self.print_traffic()

        default_headers = dict(std_headers)
        default_headers.update(self.headers)
        default_headers.update(self.update_cookies_in_headers)

        url = self._build_url()

        body = None
        if self.data is not None:
            if isinstance(self.data, (bytes, bytearray)):
                body = bytes(self.data)
            elif isinstance(self.data, str):
                body = self.data.encode("utf-8")
            elif isinstance(self.data, dict):
                body = urllib.parse.urlencode(self.data, doseq=True).encode("utf-8")
            else:
                body = str(self.data).encode("utf-8")

        last_err = None
        for _ in range(self.retries + 1):
            try:
                req = urllib.request.Request(
                    url=url,
                    data=body,
                    headers=default_headers,
                    method=self.method,
                )
                resp = urllib.request.urlopen(req, timeout=self.timeout)
                code = getattr(resp, "status", None) or resp.getcode()

                if code in (429, 503, 502, 504):
                    last_err = RuntimeError(f"HTTP {code}")
                    continue

                if self.stream:
                    return HttpResponse(resp, b"")

                data = resp.read()
                resp.close()
                return HttpResponse(resp, data)

            except urllib.error.HTTPError as e:
                if e.code in (429, 503, 502, 504):
                    last_err = RuntimeError(f"HTTP {e.code}")
                    continue
                raise
            except (urllib.error.URLError, socket.timeout) as e:
                last_err = e
                continue

        raise last_err
