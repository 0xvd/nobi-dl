from ..networking import Request
from ..utils import filename_from_title
import os
import time
from .common import ProgressPrinter


class HttpDownloader:
    def __init__(self, format, info_dict, options, logger):
        self.format = format
        self.info_dict = info_dict
        self.formats = info_dict.get("formats") or []
        self.opts = options
        self.logger = logger
        self.stdout = logger.to_stdout
        self.continue_dl = self.opts.continue_dl

    def to_screen(self, msg):
        return self.stdout(f"[http_downloader] {msg}")

    def __call__(self):
        return self.downloader()

    def _prepare_download(self, fmt):
        title = self.info_dict.get("title")
        url = fmt["url"]
        ext = fmt.get("ext", "mp4")

        filename = filename_from_title(title, url) if title else f"Unknown movie.{ext}"
        part = filename + ".part"

        resume_from = 0
        if self.continue_dl and os.path.exists(part):
            resume_from = os.path.getsize(part) or 0

        return filename, part, resume_from

    def _open_response(self, url, resume_from, headers):
        if resume_from:
            headers["Range"] = f"bytes={resume_from}-"

        resp = Request(
            url=url,
            logger=self.logger,
            method="GET",
            stream=True,
            headers=headers,
        )()

        if resume_from and getattr(resp, "status_code", None) == 200:
            headers.pop("Range", None)
            resp = Request(
                url=url,
                logger=self.logger,
                method="GET",
                stream=True,
                headers=headers,
            )()

        return resp

    def _detect_total_size(self, resp, resume_from, fmt):
        hdrs = getattr(resp, "headers", {}) or {}

        cr = hdrs.get("Content-Range") or hdrs.get("content-range")
        if cr and "/" in cr:
            try:
                return int(cr.split("/")[-1])
            except ValueError:
                pass

        cl = hdrs.get("Content-Length") or hdrs.get("content-length")
        if cl:
            try:
                size = int(cl)
                return size + resume_from if resume_from else size
            except ValueError:
                pass

        for value in ("filesize", "filesize_approx"):
            value = fmt.get(value)
            if isinstance(value, (int, float)) and value > 0:
                return int(value)

        return None

    def _download_stream(self, resp, part, resume_from, total, filename):
        progress = ProgressPrinter(self.logger)
        downloaded = resume_from
        ema_speed = None
        t0 = last_t = time.time()
        last_b = downloaded
        alpha = 0.15

        iterator = (
            resp.iter_bytes(1024 * 256)
            if hasattr(resp, "iter_bytes")
            else resp.iter_content(chunk_size=1024 * 256)
        )

        with open(part, "ab" if resume_from else "wb") as f:
            for chunk in iterator:
                if not chunk:
                    continue

                f.write(chunk)
                downloaded += len(chunk)

                now = time.time()
                if now - last_t >= 0.2:
                    dt = now - last_t
                    db = downloaded - last_b
                    speed = db / max(dt, 1e-6)

                    ema_speed = (
                        speed
                        if ema_speed is None
                        else (alpha * speed + (1 - alpha) * ema_speed)
                    )

                    eta = (
                        (total - downloaded) / ema_speed
                        if total and ema_speed
                        else None
                    )

                    progress(
                        {
                            "status": "downloading",
                            "filename": filename,
                            "downloaded_bytes": downloaded,
                            "total_bytes": total,
                            "speed": ema_speed,
                            "eta": eta,
                            "elapsed": now - t0,
                            "progress_type": "bytes",
                        }
                    )

                    last_t = now
                    last_b = downloaded

        return downloaded, time.time() - t0

    def downloader(self):
        fmt = self.format
        filename, part, resume_from = self._prepare_download(fmt)

        self.to_screen(f"Downloading format: {fmt.get('format_id')}")
        self.to_screen(f'Invoking [http] Downloader on "{fmt["url"]}"')
        self.to_screen(f"Destination: {filename}")

        headers = dict(fmt.get("https_headers") or {})
        resp = None

        try:
            resp = self._open_response(fmt["url"], resume_from, headers)
            total = self._detect_total_size(resp, resume_from, fmt)

            downloaded, elapsed = self._download_stream(
                resp, part, resume_from, total, filename
            )

            os.replace(part, filename)

            ProgressPrinter(self.logger)(
                {
                    "status": "finished",
                    "filename": filename,
                    "downloaded_bytes": downloaded,
                    "total_bytes": total,
                    "elapsed": elapsed,
                    "progress_type": "bytes",
                }
            )

        except KeyboardInterrupt:
            self.to_screen(
                "Interrupted by user. add -c or --continue for continue downloading."
            )
            raise SystemExit(130)

        finally:
            if resp and hasattr(resp, "close"):
                resp.close()
