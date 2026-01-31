from ..utils import (
    NobiDLError,
)
import time
import sys


class BestFMT:
    def __init__(self, formats: list[dict]):
        self.formats = formats or []

    def __call__(self) -> dict:
        return self.best()

    def _score(self, f: dict) -> tuple:
        vcodec = f.get("vcodec")
        acodec = f.get("acodec")
        has_av = int(
            bool(vcodec and vcodec != "none") and bool(acodec and acodec != "none")
        )

        height = f.get("height") or 0
        tbr = f.get("tbr") or 0
        filesize = f.get("filesize") or 0

        return (has_av, height, tbr, filesize)

    def best(self) -> dict:
        if not self.formats:
            raise NobiDLError("No formats found")

        return max(self.formats, key=self._score)


class ProgressPrinter:
    _ANSI = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "blue": "\033[94m",
        "yellow": "\033[93m",
        "green": "\033[92m",
        "red": "\033[91m",
        "white": "\033[97m",
    }

    def __init__(self, logger, *, is_tty=None):
        self.log = logger
        self.is_tty = sys.stderr.isatty() if is_tty is None else is_tty
        self._last = 0.0

    def _c(self, text: str, *styles: str) -> str:
        if not self.is_tty:
            return text
        codes = "".join(self._ANSI[s] for s in styles if s in self._ANSI)
        return f"{codes}{text}{self._ANSI['reset']}"

    def _fmt_bytes(self, n: int) -> str:
        units = ["B", "KiB", "MiB", "GiB", "TiB"]
        f = float(n)
        for u in units:
            if f < 1024 or u == units[-1]:
                return f"{f:.2f}{u}" if u != "B" else f"{int(f)}B"
            f /= 1024

    def _fmt_time(self, s: float | None) -> str:
        if s is None:
            return "--:--"
        s = int(s)
        if s < 0:
            return "--:--"

        d, s = divmod(s, 86400)
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)

        if d:
            return f"{d}d {h:02d}:{m:02d}:{s:02d}"
        if h:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _fmt_count(self, cur: int, total: int | None) -> str:
        if total:
            return f"{cur}/{total}"
        return f"{cur}/???"

    def _fmt_speed_frag(self, sps: float | None) -> str:
        if not sps:
            return "?? seg/s"
        return f"{sps:.2f} seg/s"

    def __call__(self, p: dict):
        now = time.time()
        if p.get("status") == "downloading" and now - self._last < 0.2:
            return
        self._last = now

        ptype = p.get("progress_type", "bytes")

        tag = "[download]"

        if ptype == "fragments":
            done = int(p.get("downloaded_fragments") or 0)
            total = p.get("total_fragments")
            speed = p.get("speed")
            eta = p.get("eta")

            pct_raw = f"{(done * 100 / total):6.2f}%" if total else "   --.-%"
            count_s = self._fmt_count(done, total)
            speed_s = self._fmt_speed_frag(speed)
            eta_s = self._fmt_time(eta)

            line = (
                f"{tag} "
                f"{self._c(f'{pct_raw}', 'blue')} "
                f"{self._c(count_s, 'white')} "
                f"at {self._c(speed_s, 'green')} "
                f"ETA {self._c(eta_s, 'yellow')}"
            )

        else:
            done = int(p.get("downloaded_bytes") or 0)
            total = p.get("total_bytes")
            speed = p.get("speed")
            eta = p.get("eta")

            pct_raw = f"{(done * 100 / total):6.2f}%" if total else "   --.-%"
            done_s = self._fmt_bytes(done)
            total_s = self._fmt_bytes(total) if total else "???"
            speed_s = (self._fmt_bytes(int(speed)) + "/s") if speed else "??/s"
            eta_s = self._fmt_time(eta)

            line = (
                f"{tag} "
                f"{self._c(f'[{pct_raw}]', 'blue')} "
                f"{self._c(f'{done_s}/{total_s}', 'white')} "
                f"at {self._c(speed_s, 'green')} "
                f"ETA {self._c(eta_s, 'yellow')}"
            )

        if self.is_tty:
            self.log.to_stderr("\r" + line + "\033[K", only_once=False, newline=False)
        else:
            self.log.to_stderr(line, only_once=False)

        if p.get("status") in ("finished", "error") and self.is_tty:
            self.log.to_stderr("\n", only_once=False, newline=False)
