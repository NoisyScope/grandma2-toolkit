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
    (the latter also for a login with an unknown user);
  * some commands finish later than their prompt: `Plugin N` returns to the prompt at once and
    the plugin's gma.feedback() text arrives afterwards, right after the prompt.
    That later text is kept in CommandResult.late and can be awaited with wait_for().
"""
from __future__ import annotations

import re
import socket
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
PROMPT_RE = re.compile(r"\[([^\[\]\r\n]+)\]>[ \t]*$")
# A prompt anywhere: output that arrives later (plugin feedback) is printed right after it,
# e.g. " [Group]>MA2KIT_PROBE feedback" (verified on 3.9.61).
ANY_PROMPT_RE = re.compile(r"\[([^\[\]\r\n]+)\]>")
ERROR_RE = re.compile(r"^.*\b(error\b.*|(illegal|unknown) command.*)$", re.IGNORECASE | re.MULTILINE)
ERROR_CODE_RE = re.compile(r"^Error #(\d+):\s*(.*)$", re.MULTILINE)
ECHO_PREFIX = "Executing : "
LOGGED_IN_RE = re.compile(r"Logged in as User '([^']*)'")
# Dialogs (verified): a question line, then numbered options with the default in brackets, e.g.
#   "ATTENTION: Please confirm! : Reload plugin engine ? :"      "[1]: Ok" / " 2 : Cancel"
#   "Overwrite Confirmation : At the import destination already exists object "x 100". :"
#        "[1]: Overwrite" / " 2 : Overwrite|All" / " 3 : Insert" / " 4 : Insert|All" / " 5 : Cancel"
# Answered by sending the option number; the console acknowledges with " - Selected <label>".
DEFAULT_OPTION_RE = re.compile(r"^\s*\[(\d+)\]:\s*(.+?)\s*$", re.MULTILINE)
DIALOG_OPTION_RE = re.compile(r"^\s*(\[)?(\d+)\]?\s*:\s*(.+?)\s*$")
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
class Dialog:
    question: str
    options: list[tuple[int, str]]  # (number, label)
    default: int | None = None

    def option(self, label: str) -> int | None:
        """Number of the option with this label (case-insensitive), e.g. "Cancel", "Overwrite"."""
        for number, text in self.options:
            if text.strip().lower() == label.lower():
                return number
        return None

    @property
    def cancel_option(self) -> int | None:
        return self.option("Cancel")


def parse_dialog(text: str) -> Dialog | None:
    """Recognise a console dialog: a question line followed by "[n]: default" and " m : other" options."""
    first = DEFAULT_OPTION_RE.search(text)
    if not first:
        return None
    lines = text[: first.start()].rstrip("\n").split("\n")
    question = next((ln.strip() for ln in reversed(lines) if ln.strip()), "")
    question = re.sub(r"^ATTENTION:\s*", "", question)
    question = re.sub(r"^Please confirm!\s*:\s*", "", question).rstrip(" :")
    options, default = [], None
    for line in text[first.start() :].lstrip("\n").split("\n"):
        m = DIALOG_OPTION_RE.match(line)
        if not m:
            if line.strip():
                break
            continue
        number = int(m.group(2))
        options.append((number, m.group(3)))
        if m.group(1):
            default = number
    return Dialog(question, options, default)


ConfirmHandler = Callable[[Dialog], "int | None"]


@dataclass
class CommandResult:
    command: str
    text: str  # cleaned reply, without the trailing prompt
    prompt: str | None  # e.g. "Channel" from "[Channel]>"
    sent: bool = True  # False in dry-run
    late: str = ""  # output that arrived after the prompt (e.g. plugin feedback)
    dialog: Dialog | None = None  # confirmation dialog the command opened, if any
    answer: str | None = None  # label of the option that was chosen

    @property
    def cancelled(self) -> bool:
        return self.dialog is not None and (self.answer or "").lower() == "cancel"

    @property
    def errors(self) -> list[str]:
        found = [m.group(0).strip() for m in ERROR_RE.finditer(self.text)]
        if self.cancelled:
            found.append(f"confirmation cancelled: {self.dialog.question}")
        return found

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


def find_echo(text: str, echo: str | None) -> int:
    """Position of the command's "Executing : ..." echo, or -1 if it has not arrived yet.

    The console normalises keywords in the echo (verified: `Lua "..."` echoes as `LUA "..."`),
    so fall back to a case-insensitive match, then to the first echo of any command.
    """
    if not echo:
        return 0
    pos = text.find(echo)
    if pos == -1:
        pos = text.lower().find(echo.lower())
    if pos == -1:
        pos = text.find(ECHO_PREFIX)
    return pos


def split_reply(text: str, echo: str | None) -> tuple[str, str, str | None, str]:
    """Split raw reply text into (before, body, prompt, after).

    `before` is unrelated output that came before the command's echo, `body` the reply up to the
    first prompt after the echo, and `after` anything printed after that prompt.
    """
    start = max(find_echo(text, echo), 0)
    before = text[:start]
    match = ANY_PROMPT_RE.search(text, start)
    if not match:
        return before, text[start:].strip("\n").rstrip(), None, ""
    body = text[start : match.start()].strip("\n").rstrip()
    after = text[match.end() :].strip()
    return before, body, match.group(1), after


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
        auto_reconnect: bool = True,
    ) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self.transcript = transcript
        self.dry_run = dry_run
        self.idle = idle  # quiet time after the prompt before a reply is considered complete
        self.auto_reconnect = auto_reconnect
        self.user: str | None = None
        self.greeting = ""
        self.prompt: str | None = None
        self.reconnects = 0
        self._sock: socket.socket | None = None
        self._secrets: list[str] = []
        self._credentials: tuple[str, str] | None = None
        self._pending = ""  # output received after the last reply's prompt, not yet consumed
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
        self._pending = ""
        greeting = self._read_reply(self.timeout, echo=None)
        if REMOTE_DISABLED in greeting:
            self.close()
            raise RemoteDisabledError(
                "Telnet is disabled on the console: Setup > Console > Global Settings > Telnet = Login Enabled"
            )
        users = LOGGED_IN_RE.findall(greeting)
        self.user = users[-1] if users else None
        self.greeting = greeting
        prompts = ANY_PROMPT_RE.findall(greeting)
        self.prompt = prompts[-1] if prompts else None
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
        self._credentials = (user, password)
        return result

    def reconnect(self) -> None:
        """Open a new connection and log in again with the last credentials."""
        if not self._credentials:
            raise MA2Error("cannot reconnect: never logged in")
        self.close()
        self.connect()
        self.login(*self._credentials)
        self.reconnects += 1
        self._log("reconnected")

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
    def send(
        self,
        command: str,
        timeout: float | None = None,
        confirm: ConfirmHandler | None = None,
    ) -> CommandResult:
        """Send one command line.

        If the console opens a confirmation dialog, `confirm(dialog)` picks the option number;
        without a handler (or when it returns None) the dialog is answered Cancel, so nothing
        is ever confirmed by accident. A cancelled dialog shows up in result.errors.
        """
        command = command.strip()
        if "\n" in command or "\r" in command:
            raise ValueError("send one command line at a time")
        masked = self._mask(command)
        self.sent_log.append(masked)
        if self.dry_run:
            self._log(f"(dry-run) >>> {masked}")
            return CommandResult(masked, "", None, sent=False)
        self._ensure_connected()
        assert self._sock is not None
        self._log(f">>> {masked}")
        try:
            self._sock.sendall((command + "\r\n").encode("utf-8"))
        except OSError as exc:
            # Nothing reached the console, so it is safe to reconnect and send again once.
            if not (self.auto_reconnect and self._credentials):
                raise MA2Error(f"send failed: {exc}") from exc
            self.reconnect()
            self._sock.sendall((command + "\r\n").encode("utf-8"))
        echo = ECHO_PREFIX + command
        raw = self._read_reply(timeout or self.timeout, echo=echo)
        if self._sock is None and ANY_PROMPT_RE.search(raw) is None:
            raise MA2Error(f"connection lost while waiting for '{masked}'; it may or may not have run")
        dialog = answer = None
        start = max(find_echo(raw, echo), 0)
        if ANY_PROMPT_RE.search(raw, start) is None and (dialog := parse_dialog(raw[start:])):
            choice = confirm(dialog) if confirm else None
            valid = {n for n, _ in dialog.options}
            if choice not in valid:
                choice = dialog.cancel_option if dialog.cancel_option is not None else max(valid)
            answer = dict(dialog.options)[choice]
            self._log(f"(dialog) {dialog.question} -> {answer}")
            self._sock.sendall(f"{choice}\r\n".encode())
            raw += self._read_reply(timeout or self.timeout, echo=None)
        before, body, prompt, after = split_reply(raw, echo)
        before, body, after = self._mask(before), self._mask(body), self._mask(after)
        if before.strip():
            self._log(f"(earlier output) {before.strip()}")
        text = strip_echo(body)
        if prompt:
            self.prompt = prompt
        self._pending = after
        self._log(text)
        if after:
            self._log(f"(after prompt) {after}")
        return CommandResult(masked, text, prompt, late=after, dialog=dialog, answer=answer)

    def wait_for(self, pattern: str | re.Pattern[str], timeout: float = 10.0) -> str:
        """Wait for output matching `pattern` (e.g. a plugin's completion marker).

        Looks at output already received after the last prompt, then keeps reading.
        Returns everything up to and including the match and consumes it.
        """
        regex = re.compile(pattern) if isinstance(pattern, str) else pattern
        if self.dry_run:
            return ""
        assert self._sock is not None, "not connected"
        raw = bytearray()
        deadline = time.monotonic() + timeout
        while True:
            text = self._pending + clean(strip_telnet(bytes(raw)).decode("utf-8", "replace"))
            match = regex.search(text)
            if match:
                self._pending = text[match.end() :]
                return self._mask(text[: match.end()])
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._pending = text
                raise MA2Timeout(f"pattern {regex.pattern!r} not seen within {timeout}s")
            self._sock.settimeout(remaining)
            try:
                chunk = self._sock.recv(65536)
            except (socket.timeout, TimeoutError):
                continue
            if not chunk:
                self._drop()
                raise MA2Error("connection closed while waiting")
            raw += chunk

    # -- internals -------------------------------------------------------
    def _ensure_connected(self) -> None:
        """Drain stray output; reconnect if the console closed the connection."""
        if self._sock is not None:
            stray = self._drain()
            if stray is None:  # closed by the console
                self._drop()
            elif stray.strip():
                self._log(f"(unsolicited) {self._mask(stray.strip())}")
        if self._sock is None:
            if not (self.auto_reconnect and self._credentials):
                raise MA2Error("not connected")
            self.reconnect()

    def _drain(self) -> str | None:
        """Read whatever is waiting without blocking. None means the connection is closed."""
        assert self._sock is not None
        raw = bytearray()
        self._sock.setblocking(False)
        try:
            while True:
                try:
                    chunk = self._sock.recv(65536)
                except (BlockingIOError, InterruptedError):
                    break
                except OSError:
                    return None
                if not chunk:
                    return None
                raw += chunk
        finally:
            if self._sock is not None:
                self._sock.setblocking(True)
        return clean(strip_telnet(bytes(raw)).decode("utf-8", "replace"))

    def _drop(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None
                self._log("connection closed by console")

    def _read_reply(self, timeout: float, echo: str | None) -> str:
        """Read until a prompt follows the command's echo, then `idle` seconds pass with no new data."""
        assert self._sock is not None
        raw = bytearray()
        deadline = time.monotonic() + timeout
        while True:
            text = clean(strip_telnet(bytes(raw)).decode("utf-8", "replace"))
            start = find_echo(text, echo)
            # done when a prompt follows the echo, or a confirmation dialog is waiting for an answer
            at_prompt = start != -1 and (
                ANY_PROMPT_RE.search(text, start) is not None or parse_dialog(text[start:]) is not None
            )
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
            except OSError:
                self._drop()
                return text
            if not chunk:  # console closed the connection
                self._drop()
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
