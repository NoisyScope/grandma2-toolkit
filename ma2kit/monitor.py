"""Read the console's system monitor stream (Telnet port 30001, no login, read-only).

Verified on 3.9.61: lines look like "22h12m16.121s : <text>". gma.echo() output from plugins, every
command typed by any user ("toolkit 3 CMD INPUT : List Plugin"), Lua engine messages and show
save messages appear here.
"""
from __future__ import annotations

import re
import socket
from collections.abc import Iterator

from .client import clean, strip_telnet

LINE_RE = re.compile(r"^(\d+h\d+m[\d.]+s)\s*:\s?(.*)$")


def parse_line(line: str) -> tuple[str | None, str]:
    match = LINE_RE.match(line)
    return (match.group(1), match.group(2)) if match else (None, line)


def stream(host: str, port: int, pattern: str | None = None, timeout: float = 5.0) -> Iterator[str]:
    """Yield monitor lines as they arrive, optionally only those matching `pattern` (regex)."""
    regex = re.compile(pattern, re.IGNORECASE) if pattern else None
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(None)
        buffer = ""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                return
            buffer += clean(strip_telnet(chunk).decode("utf-8", "replace"))
            *lines, buffer = buffer.split("\n")
            for line in lines:
                line = line.rstrip()
                if line and (regex is None or regex.search(line)):
                    yield line
