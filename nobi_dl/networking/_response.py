import json

class HttpResponse:
    def __init__(self, resp, body: bytes):
        self._resp = resp
        self._body = body

        self.headers = dict(resp.headers)
        self.status_code = getattr(resp, "status", None)

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
