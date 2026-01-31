import re
import types

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def remove_terminal_sequences(s: str) -> str:
    return ANSI_RE.sub("", s or "")


class Namespace(types.SimpleNamespace):
    def __iter__(self):
        return iter(self.__dict__.values())

    @property
    def items_(self):
        return self.__dict__.items()


Styles = Namespace(
    HEADERS="yellow",
    EMPHASIS="light blue",
    FILENAME="green",
    ID="green",
    DELIM="blue",
    ERROR="red",
    BAD_FORMAT="light red",
    WARNING="yellow",
    SUPPRESS="light black",
)
ALLOW_COLORS = True
OUT_HANDLE = types.SimpleNamespace(encoding="utf-8")

CONTROL_SEQUENCES = {
    "DOWN": "\n",
    "UP": "\033[A",
    "ERASE_LINE": "\033[K",
    "RESET": "\033[0m",
}

_COLORS = {
    "BLACK": "0",
    "RED": "1",
    "GREEN": "2",
    "YELLOW": "3",
    "BLUE": "4",
    "PURPLE": "5",
    "CYAN": "6",
    "WHITE": "7",
}


_TEXT_STYLES = {
    "NORMAL": "0",
    "BOLD": "1",
    "UNDERLINED": "4",
}


def format_text(text, f):
    f = f.upper()
    tokens = f.strip().split()

    bg_color = ""
    if "ON" in tokens:
        if tokens[-1] == "ON":
            raise SyntaxError(f"Empty background format specified in {f!r}")
        if tokens[-1] not in _COLORS:
            raise SyntaxError(f"{tokens[-1]} in {f!r} must be a color")
        bg_color = f"4{_COLORS[tokens.pop()]}"
        if tokens[-1] == "LIGHT":
            bg_color = f"0;10{bg_color[1:]}"
            tokens.pop()
        if tokens[-1] != "ON":
            raise SyntaxError(f"Invalid format {f.split(' ON ', 1)[1]!r} in {f!r}")
        bg_color = f"\033[{bg_color}m"
        tokens.pop()

    if not tokens:
        fg_color = ""
    elif tokens[-1] not in _COLORS:
        raise SyntaxError(f"{tokens[-1]} in {f!r} must be a color")
    else:
        fg_color = f"3{_COLORS[tokens.pop()]}"
        if tokens and tokens[-1] == "LIGHT":
            fg_color = f"9{fg_color[1:]}"
            tokens.pop()
        fg_style = tokens.pop() if tokens and tokens[-1] in _TEXT_STYLES else "NORMAL"
        fg_color = f"\033[{_TEXT_STYLES[fg_style]};{fg_color}m"
        if tokens:
            raise SyntaxError(f"Invalid format {' '.join(tokens)!r} in {f!r}")

    if fg_color or bg_color:
        text = text.replace(CONTROL_SEQUENCES["RESET"], f"{fg_color}{bg_color}")
        return f"{fg_color}{bg_color}{text}{CONTROL_SEQUENCES['RESET']}"
    else:
        return text


def _format_text(handle, allow_colors, text, f, fallback=None, *, test_encoding=False):
    text = str(text)
    if test_encoding:
        original_text = text
        encoding = getattr(handle, "encoding", None) or "ascii"
        text = text.encode(encoding, "ignore").decode(encoding)
        if fallback is not None and text != original_text:
            text = fallback
    return (
        format_text(text, f)
        if allow_colors is True
        else text
        if fallback is None
        else fallback
    )


def _format_out(text, f, fallback=None, *, test_encoding=False):
    return _format_text(
        OUT_HANDLE, ALLOW_COLORS, text, f, fallback, test_encoding=test_encoding
    )


def join_nonempty(*items, delim=", ", inner_delim=" "):
    if len(items) == 0:
        return ""
    out = []
    for it in items:
        if not it:
            continue
        if isinstance(it, (list, tuple)):
            out.extend([x for x in it if x])
        else:
            out.append(it)
    return (delim if delim is not None else inner_delim).join(out) if out else ""


def _list_format_headers(*headers):
    if headers:
        return [_format_out(header, Styles.HEADERS) for header in headers]
    return headers


def shorten_protocol_name(fmt: dict) -> str:
    url = fmt.get("url")
    p = "https" if "m3u8" not in url else "m3u8"
    return {
        "https": "https",
        "m3u8": "m3u8",
    }.get(p, p)


def format_decimal_suffix(num):
    if num is None:
        return None
    try:
        n = float(num)
    except Exception:
        return str(num)
    for unit, div in (("G", 1e9), ("M", 1e6), ("k", 1e3)):
        if abs(n) >= div:
            v = n / div
            return f"{v:.0f}{unit}" if v >= 10 else f"{v:.1f}{unit}"
    return f"{n:.0f}"


def format_bytes(num):
    if num is None:
        return None
    try:
        n = float(num)
    except Exception:
        return str(num)
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.1f}{units[i]}" if i else f"{int(n)}{units[i]}"


def filesize_from_tbr(tbr_kbps, duration):
    if not tbr_kbps or not duration:
        return None
    try:
        return int(float(tbr_kbps) * 1000 / 8 * float(duration))
    except Exception:
        return None


def format_resolution(f):
    if f.get("resolution"):
        return f["resolution"]
    w, h = f.get("width"), f.get("height")
    if w and h:
        return f"{w}x{h}"
    return ""


def format_field(f: dict, key=None, fmt="%s", default="", func=None, ignore=()):
    if callable(key) and func is None:
        func = key
        key = None

    val = None
    if key is None:
        val = f
    elif isinstance(key, str):
        val = f.get(key)
    else:
        val = key(f)

    if val in ignore:
        return ""
    if val is None:
        return default if default is not None else ""

    if func:
        try:
            val = func(val)
        except Exception:
            pass

    try:
        return fmt % val if fmt else str(val)
    except Exception:
        return str(val)


def simply_type(f: dict) -> str:
    ext = (f.get("ext") or "").lower()
    if ext == "zip":
        return "zipped"

    if ext in ("mp4", "mkv", "webm", "avi", "mov"):
        return "direct"

    acodec = f.get("acodec")
    vcodec = f.get("vcodec")

    if acodec is None and vcodec is None:
        return "unknown"

    if acodec and vcodec:
        return "premerged"
    if acodec and not vcodec:
        return "audio only"
    if vcodec and not acodec:
        return "video only"
    return "unknown"


def render_table(header_row, data, delim=False, extra_gap=0, hide_empty=False):
    vbar = _format_out("│", Styles.DELIM, "|", test_encoding=True)

    def width(s):
        return len(remove_terminal_sequences(str(s)).replace("\t", ""))

    def normalize_row(row, n):
        row = list(row)
        if len(row) < n:
            row += [""] * (n - len(row))
        return row[:n]

    if not header_row:
        return ""

    ncols = len(header_row)
    data = [normalize_row(r, ncols) for r in (data or [])]
    header_row = normalize_row(header_row, ncols)

    def get_max_lens(rows):
        cols = list(zip(*rows)) if rows else [[] for _ in range(ncols)]
        return [max((width(v) for v in col), default=0) for col in cols]

    if hide_empty:
        max_lens = get_max_lens(data)
        keep = [ml > 0 for ml in max_lens]
        header_row = [c for k, c in zip(keep, header_row) if k]
        data = [[c for k, c in zip(keep, r) if k] for r in data]
        ncols = len(header_row)
        data = [normalize_row(r, ncols) for r in data]

    rows = [header_row, *data]
    max_lens = get_max_lens(rows)
    extra_gap = max(1, extra_gap)

    def pad_row(row):
        out = []
        for i, text in enumerate(map(str, row)):
            if "\t" in text:
                out.append(text.replace("\t", " " * (max_lens[i] - width(text))))
            else:
                out.append(text + " " * (max_lens[i] - width(text)))
        return out

    header = pad_row(header_row)
    body = [pad_row(r) for r in data]

    lines = [
        (" " * extra_gap).join(header[:1] + sum(([vbar, c] for c in header[1:]), []))
    ]

    if delim:
        hline = _format_out("─", Styles.DELIM, "-", test_encoding=True)
        sep = hline * (len(remove_terminal_sequences(lines[0])))
        lines.append(sep)

    for r in body:
        lines.append(
            (" " * extra_gap).join(r[:1] + sum(([vbar, c] for c in r[1:]), []))
        )

    return "\n".join(s.rstrip() for s in lines)


def render_formats_table(formats, info_dict=None):
    if not formats:
        return ""

    info_dict = info_dict or {}

    table = [
        [
            _format_out(format_field(f, "format_id"), Styles.ID),
            format_field(f, "ext"),
            format_resolution(f),
            format_field(f, "fps", "\t%d", func=round),
            (
                format_field(f, "filesize", " \t%s", func=format_bytes)
                or format_field(f, "filesize_approx", "≈\t%s", func=format_bytes)
                or format_field(
                    filesize_from_tbr(f.get("tbr"), info_dict.get("duration")),
                    None,
                    _format_out("~\t%s", Styles.SUPPRESS),
                    func=format_bytes,
                )
            ),
            format_field(f, "tbr", "\t%dk", func=round),
            shorten_protocol_name(f),
            simply_type(f),
            join_nonempty(
                format_field(f, "language", "[%s]"),
                join_nonempty(
                    format_field(f, "format_note"),
                    format_field(f, "container", ignore=(None, f.get("ext"))),
                    delim=", ",
                ),
                delim=" ",
            ),
        ]
        for f in formats
        if f.get("ext") and f.get("url")
    ]

    header_line = _list_format_headers(
        "ID",
        "EXT",
        "RESOLUTION",
        "\tFPS",
        "\tFILESIZE",
        "\tTBR",
        "PROTO",
        "TYPE",
        "MORE INFO",
    )

    return render_table(
        header_line,
        table,
        delim=_format_out("─", Styles.DELIM, "-", test_encoding=True),
        hide_empty=True,
    )
