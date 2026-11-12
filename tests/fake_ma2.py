"""A tiny stand-in for the grandMA2 Telnet command line, for offline tests.

The greeting and line endings mirror what onPC 3.9.61 actually sent (see docs/04-remote-control.md).
"""
from __future__ import annotations

import re
import socket
import threading

BANNER = "\x1b[32mMMMMMMMM    MMMMMMMM     AAA\r\n" "M::::::M    M::::::M    A:::A\r\n\r\n"
GREETING = BANNER + "Logged in as User 'guest'\n\r\r [Group]>Please login !\r\n\r [Group]>"
LOGIN_RE = re.compile(r'^Login "([^"]*)" "([^"]*)"$', re.IGNORECASE)


class FakeMA2:
    def __init__(self, users: dict[str, str] | None = None, disabled: bool = False,
                 responses: dict[str, str] | None = None) -> None:
        self.users = users if users is not None else {"toolkit": "s3cret"}
        self.disabled = disabled
        self.responses = responses or {}
        self.received: list[str] = []
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
            with conn:
                self._handle(conn)

    def _handle(self, conn: socket.socket) -> None:
        if self.disabled:
            conn.sendall(b"\x1b[31m\nRemote commandline disabled\n\r")
            return
        # Telnet negotiation the client must ignore, then the greeting.
        conn.sendall(bytes([255, 251, 1]) + GREETING.encode())
        prompt = "Group"
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
                line = raw.decode()
                self.received.append(line)
                echo = f"\x1b[0mExecuting : {line}\n\r"
                error = f"\x1b[31mError : {line}\n\r"
                login = LOGIN_RE.match(line)
                if login:
                    user, pw = login.groups()
                    if self.users.get(user) == pw:
                        prompt = "Channel"
                        reply = echo + f"Logged in as User '{user}'\n\r"
                    else:
                        reply = echo + error + "Error #72: COMMAND NOT EXECUTED\n\r"
                elif line in self.responses:
                    reply = echo + self.responses[line]
                else:
                    reply = echo + error + "Error #14: OBJECT DOES NOT EXIST\n\r"
                conn.sendall(f"{reply}\n\r \r\n\r[{prompt}]>".encode())
