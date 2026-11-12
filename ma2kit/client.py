"""Client for the grandMA2 remote command line (Telnet, port 30000).

Verified on onPC 3.9.61:
  * with Telnet disabled the console sends "Remote commandline disabled" and closes;
  * with Telnet = Login Enabled it sends an ASCII-art banner,
    "Logged in as User 'guest'" and the prompt " [Group]>Please login !";
  * lines end with "\\r\\n" or "\\n\\r" and carry ANSI colour codes;
  * the prompt is "[<default keyword>]>" at the end of the output;
  * every reply starts with "Executing : <command>";
  * a failed command adds "Error : <command>" and "Error #<n>: <MESSAGE>",
    e.g. "Error #14: OBJECT DOES NOT EXIST", "Error #72: COMMAND NOT EXECUTED"
    (the latter also for a login with an unknown user).
"""
from __future__ import annotations

import re
import socket
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
PROMPT_RE = re.compile(r"\[([^\[\]\r\n]+)\]>[ \t]*$")
ERROR_RE = re.compile(r"^.*\b(error\b.*|(illegal|unknown) command.*)$", re.IGNORECASE | re.MULTILINE)
ERROR_CODE_RE = re.compile(r"^Error #(\d+):\s*(.*)$", re.MULTILINE)
ECHO_PREFIX = "Executing : "
LOGGED_IN_RE = re.compile(r"Logged in as User '([^']*)'")
REMOTE_DISABLED = "Remote commandline disabled"

# Telnet protocol bytes
_IAC, _SB, _SE = 255, 250, 240

# Commands that need an explicit confirmation before they are sent.
# MA accepts abbreviated keywords, so match on a minimum prefix.
_RISKY_PREFIXES = {
    "del": "deletes show data",
    "newsh": "replaces the loaded show",
    "loadsh": "replaces the loaded show",
    "shutd": "shuts the console down",
    "reboot": "reboots the console",
    "restart": "restarts the console",
}


class MA2Error(Exception):
    """Base error for console communication."""


class RemoteDisabledError(MA2Error):
    """Telnet is set to Disabled in Setup > Console > Global Settings."""


class LoginError(MA2Error):
    """The console did not confirm the login."""


class MA2Timeout(MA2Error):
    """The console did not return to its prompt in time."""


def strip_telnet(data: bytes) -> bytes:
    """Remove Telnet negotiation sequences (IAC ...) from raw bytes."""
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        if b != _IAC:
            out.append(b)
            i += 1
            continue
        if i + 1 >= n:
            break
        cmd = data[i + 1]
        if cmd == _IAC:
            out.append(_IAC)
            i += 2
        elif cmd == _SB:
            end = data.find(bytes([_IAC, _SE]), i + 2)
            i = n if end == -1 else end + 2
        elif 251 <= cmd <= 254:  # WILL / WONT / DO / DONT + option
            i += 3
        else:
            i += 2
    return bytes(out)


def clean(text: str) -> str:
    """Strip ANSI codes and normalise MA's mixed line endings to "\\n"."""
    text = ANSI_RE.sub("", text)
    return text.replace("\r\n", "\n").replace("\n\r", "\n").replace("\r", "\n")


def risky_reason(command: str) -> str | None:
    """Return why a command needs confirmation, or None if it is not flagged."""
    lowered = command.strip().lower()
    if "/nc" in lowered.replace(" ", ""):
        return "uses /nc (no confirmation)"
    first = lowered.split(maxsplit=1)[0] if lowered else ""
    for prefix, reason in _RISKY_PREFIXES.items():
        if first.startswith(prefix):
            return reason
    return None


@dataclass
class CommandResult:
    command: str
    text: str  # cleaned reply, without the trailing prompt
    prompt: str | None  # e.g. "Channel" from "[Channel]>"
    sent: bool = True  # False in dry-run

    @property
    def errors(self) -> list[str]:
        return [m.group(0).strip() for m in ERROR_RE.finditer(self.text)]

    @property
    def error_code(self) -> tuple[int, str] | None:
        """The console's "Error #<n>: <MESSAGE>" line, if any."""
        match = ERROR_CODE_RE.search(self.text)
        return (int(match.group(1)), match.group(2).strip()) if match else None

    @property
    def ok(self) -> bool:
        return self.sent and not self.errors


def split_prompt(text: str) -> tuple[str, str | None]:
    """Split a reply into (body, prompt); the body loses trailing blank lines."""
    match = PROMPT_RE.search(text)
    body, prompt = (text[: match.start()], match.group(1)) if match else (text, None)
    return body.strip("\n").rstrip(), prompt


def strip_echo(text: str) -> str:
    """Drop the console's "Executing : <command>" first line."""
    first, sep, rest = text.partition("\n")
    return rest if first.startswith(ECHO_PREFIX) else text


class MA2Client:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 30000,
        timeout: float = 5.0,
        transcript: Path | None = None,
        dry_run: bool = False,
        idle: float = 0.3,
    ) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self.transcript = transcript
        self.dry_run = dry_run
        self.idle = idle  # quiet time after the prompt before a reply is considered complete
        self.user: str | None = None
        self.greeting = ""
        self.prompt: str | None = None
        self._sock: socket.socket | None = None
        self._secrets: list[str] = []
        self.sent_log: list[str] = []  # commands sent (or recorded in dry-run), masked

    # -- context manager -------------------------------------------------
    def __enter__(self) -> "MA2Client":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- connection ------------------------------------------------------
    def connect(self) -> str:
        if self.dry_run:
            self._log(f"(dry-run) connect {self.host}:{self.port}")
            return ""
        self._log(f"connect {self.host}:{self.port}")
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        greeting = self._read_reply(self.timeout)
        if REMOTE_DISABLED in greeting:
            self.close()
            raise RemoteDisabledError(
                "Telnet is disabled on the console: Setup > Console > Global Settings > Telnet = Login Enabled"
            )
        users = LOGGED_IN_RE.findall(greeting)
        self.user = users[-1] if users else None
        self.greeting = greeting
        _, self.prompt = split_prompt(greeting)
        return greeting

    def login(self, user: str, password: str) -> CommandResult:
        if '"' in user or '"' in password:
            raise ValueError('user name and password must not contain a double quote (")')
        if password:
            self._secrets.append(password)
        result = self.send(f'Login "{user}" "{password}"')
        if self.dry_run:
            self.user = user
            return result
        users = LOGGED_IN_RE.findall(result.text)
        if not users or users[-1] != user:
            code = result.error_code
            detail = f"Error #{code[0]}: {code[1]}" if code else (result.text.strip() or "no reply to Login")
            raise LoginError(f"{detail} (check user name and password)")
        self.user = user
        return result

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            finally:
                self._sock = None
                self._log("disconnect")

    @property
    def connected(self) -> bool:
        return self._sock is not None

    # -- commands --------------------------------------------------------
    def send(self, command: str, timeout: float | None = None) -> CommandResult:
        command = command.strip()
        if "\n" in command or "\r" in command:
            raise ValueError("send one command line at a time")
        masked = self._mask(command)
        self.sent_log.append(masked)
        if self.dry_run:
            self._log(f"(dry-run) >>> {masked}")
            return CommandResult(masked, "", None, sent=False)
        if not self._sock:
            raise MA2Error("not connected")
        self._log(f">>> {masked}")
        self._sock.sendall((command + "\r\n").encode("utf-8"))
        reply = self._mask(self._read_reply(timeout or self.timeout))
        text, prompt = split_prompt(reply)
        text = strip_echo(text)
        if prompt:
            self.prompt = prompt
        self._log(text)
        return CommandResult(masked, text, prompt)

    # -- internals -------------------------------------------------------
    def _read_reply(self, timeout: float) -> str:
        """Read until the console shows its prompt and then stays quiet for `idle` seconds."""
        assert self._sock is not None
        raw = bytearray()
        deadline = time.monotonic() + timeout
        while True:
            text = clean(strip_telnet(bytes(raw)).decode("utf-8", "replace"))
            at_prompt = PROMPT_RE.search(text) is not None
            now = time.monotonic()
            if now >= deadline:
                if at_prompt:
                    return text
                raise MA2Timeout(f"no prompt after {timeout}s; partial reply: {text[-300:]!r}")
            self._sock.settimeout(min(self.idle, deadline - now) if at_prompt else deadline - now)
            try:
                chunk = self._sock.recv(65536)
            except (socket.timeout, TimeoutError):
                if at_prompt:
                    return text
                continue
            if not chunk:  # console closed the connection
                self._sock.close()
                self._sock = None
                return text
            raw += chunk

    def _mask(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, "****")
        return text

    def _log(self, message: str) -> None:
        if not self.transcript:
            return
        self.transcript.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().isoformat(timespec="seconds")
        with self.transcript.open("a", encoding="utf-8") as fh:
            for line in self._mask(message).splitlines() or [""]:
                fh.write(f"{stamp} {line}\n")
