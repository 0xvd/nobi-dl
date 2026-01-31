from ..networking import Request
from .common import ProgressPrinter
from ..utils import filename_from_title
import os
import time
import json


class HlsDL:
    def __init__(self, format, info_dict, options, logger):
        self.info_dict = info_dict
        self.format = format
        self.opts = options
        self.logger = logger
        self.to_stdout = logger.to_stdout
        self.continue_dl = self.opts.continue_dl
        self.printer = ProgressPrinter(self.logger)

    def __call__(self):
        return self.downloader_hls()

    def to_screen(self, msg):
        return self.to_stdout(f"[hls_native] {msg}")

    def extract_all_hls_fragments(self, text: str) -> list[str]:
        fragments = []
        lines = text.splitlines()
        expect_url = False

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF"):
                expect_url = True
                continue

            if expect_url and not line.startswith("#"):
                fragments.append(line)
                expect_url = False

        return fragments

    def hls_data(self, url, headers=None):
        headers = headers or {}
        self.to_screen("Downloading m3u8 information")
        hls_data = Request(url, headers=headers)()
        hls_data = hls_data.text
        return hls_data

    def nobidl_filename(self, filename):
        filename = filename.replace(".part", "") if ".part" in filename else filename
        return filename + ".nobidl"

    def read_nobidl_data(self, filename):
        if not os.path.exists(filename):
            return {}

        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def max_existing_fragment(self, filename):
        base = filename + ".part-Frag"
        found = []

        for f in os.listdir("."):
            if f.startswith(os.path.basename(base)) and f.endswith(".part"):
                try:
                    idx = int(f.split("Frag")[1].split(".")[0])
                    found.append(idx)
                except Exception:
                    pass

        return max(found) if found else None

    def check_continue_dl_and_files(self, filename):
        if not self.continue_dl:
            return 0

        nobidl = self.nobidl_filename(filename)
        nobi_data = self.read_nobidl_data(nobidl)
        disk_idx = self.max_existing_fragment(filename)
        if not nobi_data:
            return (disk_idx + 1) if disk_idx is not None else 0
        json_idx = nobi_data.get("current_fragment", 0)
        if disk_idx is None:
            return json_idx

        return min(json_idx, disk_idx + 1)

    def write_nobi_data(self, filename, curr_frag):
        nobi_filename = (
            self.nobidl_filename(filename)
            if not filename.endswith(".nobidl")
            else filename
        )

        tmp = nobi_filename + ".tmp"
        with open(tmp, "w") as wr:
            json.dump(
                {
                    "note": "Do not delete this file if you want to resume your download",
                    "current_fragment": curr_frag,
                    "written_by": "NOBI_DL",
                },
                wr,
                indent=2,
            )

        os.replace(tmp, nobi_filename)
        return True

    def frag_filename(self, index: int) -> str:
        return f"Frag{index:06d}.part"

    def remove_already_downloaded_fragments(
        self,
        total_frag: list,
        last_idx_frag: int | None,
    ) -> list:
        if last_idx_frag is None:
            return total_frag
        return total_frag[last_idx_frag + 1 :]

    def write_chunk_in_file(self, resp, filename):
        with open(filename, "ab") as f:
            it = getattr(resp, "iter_bytes", None)
            if it:
                for chunk in it(1024 * 64):
                    if chunk:
                        f.write(chunk)
            else:
                for chunk in resp.iter_content(1024 * 64):
                    if chunk:
                        f.write(chunk)

    def remove_frag_file(self, filename):
        os.remove(filename)

    def downloader_hls(self):
        try:
            bfmt = self.format
            title = self.info_dict.get("title")
            url = bfmt.get("url")
            ext = "mp4"
            format_id = bfmt.get("format_id")

            filename = (
                filename_from_title(title, url, ext)
                if title
                else f"Unknown_movie.{ext}"
            )
            part = filename + ".hls.part"

            self.to_screen(f"Downloading format: {format_id}")
            self.to_screen(f'Invoking Downloader on "{url}"')
            self.to_screen(f"Destination: {filename}")

            headers = bfmt.get("http_headers") or {}

            hls_data = self.hls_data(url, headers=headers)
            all_fragments = self.extract_all_hls_fragments(hls_data)

            total_frags = len(all_fragments)
            self.to_screen(f"Total Fragments: {total_frags}")

            resume_idx = self.check_continue_dl_and_files(filename)
            if resume_idx:
                self.to_screen(f"Resume at {resume_idx} fragment")
            fragments = self.remove_already_downloaded_fragments(
                all_fragments, resume_idx
            )

            downloaded = resume_idx

            last_t = time.time()
            last_done = resume_idx
            ema_speed = None
            alpha = 0.2
            for idx, frag_url in enumerate(fragments, start=resume_idx):
                frag_file = self.frag_filename(idx)

                resp = Request(frag_url, headers=headers, stream=True)()
                self.write_chunk_in_file(resp, frag_file)

                with open(part, "ab") as out, open(frag_file, "rb") as frag:
                    out.write(frag.read())

                self.remove_frag_file(frag_file)
                self.write_nobi_data(filename, idx)

                downloaded += 1
                now = time.time()
                dt = now - last_t
                df = (idx + 1) - last_done

                if dt > 0:
                    inst_speed = df / dt
                    if ema_speed is None:
                        ema_speed = inst_speed
                    else:
                        ema_speed = alpha * inst_speed + (1 - alpha) * ema_speed
                else:
                    inst_speed = None

                eta = (
                    ((total_frags - (idx + 1)) / ema_speed)
                    if ema_speed and ema_speed > 0
                    else None
                )

                self.printer(
                    {
                        "status": "downloading",
                        "progress_type": "fragments",
                        "downloaded_fragments": idx + 1,
                        "total_fragments": total_frags,
                        "speed": ema_speed,
                        "eta": eta,
                    }
                )

                last_t = now
                last_done = idx + 1

            os.replace(part, filename)
            os.remove(self.nobidl_filename(filename))
            self.printer(
                {
                    "status": "finished",
                    "progress_type": "fragments",
                    "downloaded_fragments": total_frags,
                    "total_fragments": total_frags,
                    "speed": None,
                    "eta": None,
                }
            )

        except Exception:
            raise SystemExit(130)

        try:
            if resp and getattr(resp, "close", None):
                resp.close()
        except Exception:
            pass

        except KeyboardInterrupt:
            if self.printer:
                self.printer(
                    {
                        "status": "error",
                        "progress_type": "fragments",
                        "downloaded_fragments": total_frags,
                        "total_fragments": total_frags,
                        "speed": None,
                        "eta": None,
                    }
                )
            self.to_screen(
                "Interrupted by user. add -c or --continue for continue downloading."
            )
            raise SystemExit(130)
