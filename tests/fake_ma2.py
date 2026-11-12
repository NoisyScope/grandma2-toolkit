"""A tiny stand-in for the grandMA2 Telnet command line, for offline tests.

Greeting, echo, error, dialog and late-output formats mirror what onPC 3.9.61 actually sent
(see docs/04-remote-control.md).
"""
from __future__ import annotations

import re
import socket
import threading
import time

BANNER = "\x1b[32mMMMMMMMM    MMMMMMMM     AAA\r\n" "M::::::M    M::::::M    A:::A\r\n\r\n"
GREETING = BANNER + "Logged in as User 'guest'\n\r\r [Group]>Please login !\r\n\r [Group]>"
LOGIN_RE = re.compile(r'^Login "([^"]*)" "([^"]*)"$', re.IGNORECASE)


class FakeMA2:
    def __init__(
        self,
        users: dict[str, str] | None = None,
        disabled: bool = False,
        responses: dict[str, str] | None = None,
        late: dict[str, str] | None = None,
        dialogs: dict[str, str] | None = None,
    ) -> None:
        self.users = users if users is not None else {"toolkit": "s3cret"}
        self.disabled = disabled
        self.responses = responses or {}
        self.late = late or {}  # command -> text printed after the prompt (like plugin feedback)
        self.dialogs = dialogs or {}  # command -> question of a "Please confirm!" dialog
        self.received: list[str] = []
        self.connections = 0
        self._srv = socket.socket()
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen()
        self.port = self._srv.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def __enter__(self) -> "FakeMA2":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._srv.close()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            self.connections += 1
            with conn:
                self._handle(conn)

    def _lines(self, conn: socket.socket):
        buf = b""
        while True:
            try:
                chunk = conn.recv(4096)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            while b"\r\n" in buf:
                raw, buf = buf.split(b"\r\n", 1)
                yield raw.decode()

    def _handle(self, conn: socket.socket) -> None:
        if self.disabled:
            conn.sendall(b"\x1b[31m\nRemote commandline disabled\n\r")
            return
        # Telnet negotiation the client must ignore, then the greeting.
        conn.sendall(bytes([255, 251, 1]) + GREETING.encode())
        prompt = "Group"
        path: list[str] = []  # `cd` location; the prompt shows it as "A/B >" (verified on 3.9.61)
        pending_dialog: str | None = None
        for line in self._lines(conn):
            self.received.append(line)
            if pending_dialog is not None:
                label = {"1": "Ok", "2": "Cancel"}.get(line, "Cancel")
                conn.sendall(f" - Selected {label}\n\r [{prompt}]>".encode())
                pending_dialog = None
                continue
            if line == "DROP":  # test hook: the console closes the connection
                return
            # The console normalises keywords in its echo, e.g. Lua -> LUA.
            shown = re.sub(r"^lua\b", "LUA", line, flags=re.IGNORECASE)
            echo = f"\x1b[0mExecuting : {shown}\n\r"
            error = f"\x1b[31mError : {line}\n\r"
            if line in self.dialogs:
                pending_dialog = line
                conn.sendall(
                    (echo + f"\nATTENTION: Please confirm! : {self.dialogs[line]} :\n\r[1]: Ok\n\r 2 : Cancel\n\r").encode()
                )
                continue
            cd = re.match(r"^cd\s*(.*)$", line, re.IGNORECASE)
            if cd:
                target = cd.group(1).strip().strip('"')
                if target == "/":
                    path = []
                elif target == "..":
                    path = path[:-1]
                elif target:
                    path = path + [target]
                where = f"{'/'.join(path)} >" if path else f" [{prompt}]>"
                conn.sendall(f"\x1b[0mExecuting : ChangeDest {cd.group(1).strip()}\n\r\n\r{where}".encode())
                continue
            login = LOGIN_RE.match(line)
            if login:
                user, pw = login.groups()
                if self.users.get(user) == pw:
                    prompt = "Channel"
                    reply = echo + f"Logged in as User '{user}'\n\r"
                else:
                    reply = echo + error + "Error #72: COMMAND NOT EXECUTED\n\r"
            elif line in self.responses or line in self.late:
                reply = echo + self.responses.get(line, "")
            else:
                reply = echo + error + "Error #14: OBJECT DOES NOT EXIST\n\r"
            where = f"{'/'.join(path)} >" if path else f" [{prompt}]>"
            conn.sendall(f"{reply}\n\r \r\n\r{where}".encode())
            if line in self.late:
                time.sleep(0.05)
                conn.sendall(self.late[line].encode())
