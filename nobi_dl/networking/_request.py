import requests
from requests import exceptions as req_exc
import http.client
from ._curl_cffi import Curl_cfiiRH

GLOBAL_SESSION = requests.Session()


class RequestsRH:
    def __init__(
        self,
        url,
        headers=None,
        cookies=None,
        query=None,
        data=None,
        timeout=20,
        method=None,
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
        self.data = data or {}
        self.timeout = timeout or 20
        self.method = method or "GET"
        self.retries = retries
        self.stream = stream

    def __call__(self):
        return self._request()

    def _print_verbose(self, msg):
        if self.verbose is True:
            return self.logger.to_stdout(msg)

    def print_traffic(self):
        if self.verbose is False:
            return
        self._print_verbose(f"Sending Request via {requests.__name__}")
        http.client.HTTPSConnection.debuglevel = 1
        http.client.HTTPConnection.debuglevel = 1

    def _request(self):
        from ._request_handler import std_headers

        self.print_traffic()
        default_headers = dict(std_headers)
        if self.headers:
            default_headers.update(self.headers)

        last_err = None
        for _ in range(self.retries + 1):
            try:
                resp = GLOBAL_SESSION.request(
                    self.method,
                    self.url,
                    cookies=self.cookies,
                    params=self.query,
                    data=self.data,
                    timeout=self.timeout,
                    headers=default_headers,
                    stream=self.stream,
                )
                GLOBAL_SESSION.cookies.update(resp.cookies)
                if resp.status_code in (429, 503, 502, 504):
                    last_err = RuntimeError(f"HTTP {resp.status_code}")
                    continue

                return resp

            except req_exc.Timeout as e:
                last_err = e
                continue

            except req_exc.ConnectionError:
                self.logger.to_stdout("[network] Connection Error Forcing to Curl cffi")
                return Curl_cfiiRH(
                    self.url,
                    self.method,
                    None,
                    self.headers,
                    self.cookies,
                    self.query,
                    self.data,
                    self.timeout,
                    self.retries,
                    self.verbose,
                    self.logger,
                    self.stream,
                )()

        raise last_err
