"""Make the terminal "screenshots" in docs/images/ by running ma2kit with scripted input.

    python tools/screenshots.py            # needs the console running and config.toml filled in

Each scene runs the real menu or command against the console. Typed answers are fed to `input()`
and shown in the picture as if typed. The loaded show's name, this computer's name and the Windows
user name are replaced before anything is written, so the images can go into a public repository.
Only read-only actions are used.
"""
from __future__ import annotations

import builtins
import contextlib
import getpass
import io
import os
import re
import socket
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ma2kit import cli  # noqa: E402

OUT = ROOT / "docs" / "images"
TYPED_START, TYPED_END = "\x01", "\x02"  # marks typed text inside the captured output
MAX_COLS = 120
MAX_ROWS = 46

# name, title, argv, typed answers in order, the picture ends at the first line starting with this
SCENES = [
    ("menu-main", "Main menu", ["menu"], ["0"], None),
    ("menu-summary", "Show summary", ["menu"], ["2", "", "0"], "Press Enter"),
    ("menu-check", "Check the show", ["menu"], ["6", "", "0"], "Press Enter"),
    ("menu-free", "Find free pool slots", ["menu"], ["7", "Macro", "5", "", "0"], "Press Enter"),
    ("menu-plugins", "Plugins submenu", ["menu"], ["9", "1", "0", "0"], "Other plugins"),
    ("cli-doctor", "ma2kit doctor", ["doctor"], [], None),
]


def capture(argv: list[str], answers: list[str]) -> str:
    feed = iter(answers)
    real_input = builtins.input

    def fake_input(prompt: str = "") -> str:
        try:
            answer = next(feed)
        except StopIteration:
            raise EOFError from None
        sys.stdout.write(f"{prompt}{TYPED_START}{answer}{TYPED_END}\n")
        return answer

    buf = io.StringIO()
    builtins.input = fake_input
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            cli.main(argv)
    finally:
        builtins.input = real_input
    return buf.getvalue()


def private_words() -> list[tuple[str, str]]:
    """Text that must not end up in the public images, with its replacement."""
    words: list[tuple[str, str]] = []
    cfg = cli.load_config(None)
    try:
        client = cli._connect_and_login(cfg, dry_run=False)
        show = cli.ShowModel(client).var("SHOWFILE")
        client.close()
        if show:
            words.append((show, "demo_show"))
    except Exception as exc:  # no console: the scenes would fail anyway
        sys.exit(f"cannot read the loaded show: {exc}")
    home = str(Path.home())
    user = getpass.getuser()
    words += [(home, r"C:\Users\you"), (rf"\Users\{user}", r"\Users\you"), (socket.gethostname(), "PC")]
    return [(w, r) for w, r in words if w]


def redact(text: str, words: list[tuple[str, str]]) -> str:
    for word, repl in words:
        text = re.sub(re.escape(word), lambda _m: repl, text, flags=re.IGNORECASE)
    return text


def tidy(text: str, until: str | None) -> list[str]:
    lines = text.replace("\r", "").split("\n")
    if until:
        end = next((i for i, ln in enumerate(lines) if ln.lstrip().startswith(until)), len(lines) - 1)
        lines = lines[: end + 1]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if len(lines) > MAX_ROWS:
        cut = len(lines) - MAX_ROWS + 1
        lines = lines[: MAX_ROWS - 6] + [f"   … {cut} more lines …"] + lines[-5:]
    return [line if len(line) <= MAX_COLS else line[: MAX_COLS - 1] + "…" for line in lines]


# -- SVG ---------------------------------------------------------------------
BG, FG, DIM, TYPED, HEAD, ERR, OK = "#1e1f26", "#d6d8df", "#8a8f9c", "#7fd4ff", "#ffcf6b", "#ff7b72", "#7ee08f"
CH_W, LINE_H, PAD, BAR = 8.4, 19, 18, 34


def line_color(line: str) -> str:
    plain = line.replace(TYPED_START, "").replace(TYPED_END, "")
    s = plain.strip()
    if s.startswith("==") or s.startswith("ma2kit - grandMA2"):
        return HEAD
    if s.lower().startswith(("error", "! ", "fail")) or "Error #" in s:
        return ERR
    if s.startswith(("ok ", "OK ", "✔")) or s.startswith("[ok]"):
        return OK
    if s.startswith("Press Enter"):
        return DIM
    return FG


def render_line(line: str, y: float) -> str:
    color = line_color(line)
    parts = re.split(f"({TYPED_START}[^{TYPED_END}]*{TYPED_END})", line)
    spans = []
    for part in parts:
        if not part:
            continue
        if part.startswith(TYPED_START):
            text = part[1:-1] or "⏎"
            spans.append(f'<tspan fill="{TYPED}" font-weight="bold">{escape(text)}</tspan>')
        else:
            spans.append(f'<tspan fill="{color}">{escape(part)}</tspan>')
    return f'<text x="{PAD}" y="{y:.0f}" xml:space="preserve">{"".join(spans)}</text>'


def to_svg(lines: list[str], title: str) -> str:
    cols = max([len(re.sub(f"[{TYPED_START}{TYPED_END}]", "", ln)) for ln in lines] + [60])
    width = int(cols * CH_W + PAD * 2)
    height = int(BAR + PAD + len(lines) * LINE_H + PAD / 2)
    body = "\n".join(render_line(ln, BAR + PAD + i * LINE_H + 12) for i, ln in enumerate(lines))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">
<rect width="{width}" height="{height}" rx="8" fill="{BG}"/>
<rect width="{width}" height="{BAR}" rx="8" fill="#2b2d36"/><rect y="{BAR - 8}" width="{width}" height="8" fill="#2b2d36"/>
<circle cx="18" cy="17" r="6" fill="#ff5f57"/><circle cx="38" cy="17" r="6" fill="#febc2e"/><circle cx="58" cy="17" r="6" fill="#28c840"/>
<text x="{width / 2:.0f}" y="22" fill="{DIM}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13" text-anchor="middle">{escape(title)}</text>
<g font-family="Cascadia Mono, Consolas, Menlo, 'DejaVu Sans Mono', monospace" font-size="14">
{body}
</g>
</svg>
"""


def main() -> int:
    os.chdir(ROOT)  # config.toml is looked up here
    words = private_words()
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])
    for name, title, argv, answers, until in SCENES:
        if only and name not in only:
            continue
        text = redact(capture(argv, answers), words)
        lines = tidy(text, until)
        (OUT / f"{name}.svg").write_text(to_svg(lines, f"ma2kit  —  {title}"), encoding="utf-8")
        print(f"wrote docs/images/{name}.svg ({len(lines)} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
