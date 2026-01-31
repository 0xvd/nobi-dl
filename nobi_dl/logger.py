import sys
from .utils import NobiDLError


class Log:
    def __init__(self, params=None, out=None, err=None):
        self.params = params
        self._out = out or sys.stdout
        self._err = err or sys.stderr
        self._printed_once = set()
        self._ctx_ie = None

    def _param(self, key, default=None):
        p = self.params
        if p is None:
            return default
        if isinstance(p, dict):
            return p.get(key, default)
        return getattr(p, key, default)

    def _write(self, s, stream, only_once=False):
        if only_once:
            if s in self._printed_once:
                return
            self._printed_once.add(s)
        stream.write(s)
        stream.flush()

    def to_stdout(self, s: str, *, only_once=False, newline=True):
        if s is None:
            return
        if not isinstance(s, str):
            s = str(s)
        if newline and not s.endswith("\n"):
            s += "\n"
        self._write(s, stream=self._out, only_once=only_once)

    def to_stderr(self, s: str, *, only_once=False, newline=True):
        if s is None:
            return
        if newline and not s.endswith("\n"):
            s += "\n"
        self._write(s, stream=self._err, only_once=only_once)

    def set_ie(self, ie, suffix=None):
        self._ctx_ie = ie
        self.suffix = suffix

    def _ie(self) -> str:
        ie = self._ctx_ie
        if not ie:
            return ""
        name = getattr(ie, "_IE_NAME", None) or ie.__class__.__name__
        if self.suffix is not None:
            return f"[{name}][{self.suffix}] "
        return f"[{name}] "

    def to_screen(self, message, *, only_once=False):
        if message is None:
            return
        if self._param("quiet", False) and not self._param("verbose", 0):
            return
        ie = self._ie()
        if not ie:
            ie = ""
        self.to_stdout(f"{ie}{message}", only_once=only_once)

    def write_debug(self, message):
        if message is None:
            return
        if self._param("verbose", 0):
            self.to_stderr(f"[debug] {message}")

    def warning(self, message: str):
        prefix = "[WARNING]"
        if getattr(self._err, "isatty", lambda: False)():
            prefix = "\033[33m[WARNING]\033[0m"
        self.to_stderr(f"{prefix}: {message}", only_once=True)

    def error(self, message: str, fatal=False):
        if fatal is True:
            self.warning(message=message)
        raise NobiDLError(msg=message)
