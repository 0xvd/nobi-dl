from ._urllib import UrllibRH
from ..utils import NobiDLError
import random


def random_user_agent():
    USER_AGENT_TMPL = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{} Safari/537.36"
    CHROME_MAJOR_VERSION_RANGE = (137, 143)
    return USER_AGENT_TMPL.format(
        f"{random.randint(*CHROME_MAJOR_VERSION_RANGE)}.0.0.0"
    )


std_headers = {
    "User-Agent": random_user_agent(),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-us,en;q=0.5",
    "Sec-Fetch-Mode": "navigate",
}


class RequestPrefrence:
    def __call__(self):
        return self._handler_prefrenece()

    def _handler_prefrenece(self):
        try:
            from ._request import RequestsRH

            return RequestsRH
        except ImportError:
            pass

        try:
            from ._curl_cffi import Curl_cfiiRH

            return Curl_cfiiRH
        except ImportError:
            pass

        return UrllibRH


class Request:
    def __init__(
        self,
        url,
        headers=None,
        cookies=None,
        query=None,
        data=None,
        timeout=20,
        method="GET",
        retries=3,
        verbose=False,
        logger=None,
        impersonate=None,
        stream=False,
    ):
        self.logger = logger
        self.verbose = verbose
        self.url = url
        self.cookies = cookies or {}
        self.headers = headers or {}
        self.query = query or {}
        self.data = data or {}
        self.timeout = timeout or 20
        self.method = method or "GET"
        self.retries = retries
        self.impersonate = impersonate
        self.stream = stream

    def __call__(self):
        return self._request()

    def _client_cls(self):
        return RequestPrefrence()()

    def _request(self):
        Handler = self._client_cls()

        kw = dict(
            url=self.url,
            verbose=self.verbose,
            logger=self.logger,
            headers=self.headers,
            cookies=self.cookies,
            query=self.query,
            data=self.data,
            timeout=self.timeout,
            method=self.method,
            retries=self.retries,
            stream=self.stream,
        )

        if Handler == "Curl_cfiiRH":
            from ._curl_cffi import ImpersonateTargets

            it = ImpersonateTargets(self.logger)
            if self.impersonate:
                imp = it._de_label(self.impersonate)
                if imp not in it.all_targets:
                    raise NobiDLError(
                        f'Impersonate target "{self.impersonate}" is not available.'
                        f" See --list-impersonate-targets for available targets."
                        f" This request requires browser impersonation, however you may be missing dependencies"
                        f" required to support this target."
                    )
                kw["impersonate"] = imp

        return Handler(**kw)()
