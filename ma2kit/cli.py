"""ma2kit command line."""
from __future__ import annotations

import argparse
import re
import socket
import sys
from pathlib import Path

from . import __version__
from .client import (
    MA2Client,
    MA2Error,
    LoginError,
    RemoteDisabledError,
    risky_reason,
)
from .config import Config, load_config

EXPECTED_VERSION = "3.9.61"


def _client(cfg: Config, dry_run: bool) -> MA2Client:
    return MA2Client(cfg.host, cfg.port, cfg.timeout, cfg.transcript, dry_run=dry_run)


def _connect_and_login(cfg: Config, dry_run: bool) -> MA2Client:
    if not cfg.password and not dry_run:
        raise MA2Error("no password configured: fill in [console] password in config.toml")
    client = _client(cfg, dry_run)
    client.connect()
    client.login(cfg.user, cfg.password)
    return client


def _confirm(question: str) -> bool:
    try:
        return input(f"{question} [y/N] ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def _print_result(result) -> None:
    if not result.sent:
        print(f"(dry-run) {result.command}")
        return
    if result.text:
        print(result.text)
    for err in result.errors:
        print(f"! {err}", file=sys.stderr)


# -- commands ------------------------------------------------------------
def cmd_doctor(cfg: Config, args: argparse.Namespace) -> int:
    ok = True

    def report(good: bool | None, label: str, detail: str = "") -> None:
        nonlocal ok
        mark = {True: "OK  ", False: "FAIL", None: "--  "}[good]
        if good is False:
            ok = False
        print(f"[{mark}] {label}" + (f": {detail}" if detail else ""))

    report(cfg.source is not None, "config file", str(cfg.source) if cfg.source else "not found, using defaults")
    report(bool(cfg.password) or None, "password set", "yes" if cfg.password else "no (login check skipped)")

    try:
        with socket.create_connection((cfg.host, cfg.port), timeout=cfg.timeout):
            pass
        report(True, "console reachable", f"{cfg.host}:{cfg.port}")
    except OSError as exc:
        report(False, "console reachable", f"{cfg.host}:{cfg.port} ({exc}); is onPC running?")
        return 1

    client = _client(cfg, dry_run=False)
    try:
        client.connect()
        report(True, "Telnet enabled", f"greeted as '{client.user}', prompt [{client.prompt}]")
    except RemoteDisabledError as exc:
        report(False, "Telnet enabled", str(exc))
        return 1
    except MA2Error as exc:
        report(False, "Telnet greeting", str(exc))
        return 1

    with client:
        if not cfg.password:
            return 0 if ok else 1
        try:
            client.login(cfg.user, cfg.password)
            report(True, "login", f"logged in as '{cfg.user}'")
        except LoginError as exc:
            report(False, "login", f"console replied: {exc}")
            return 1

        result = client.send("ListVar")
        version = _var(result.text, "VERSION")
        if version:
            report(version.startswith(EXPECTED_VERSION), "software version", version)
        else:
            report(None, "software version", "could not read $VERSION from ListVar")
        show = _var(result.text, "SHOWFILE")
        report(None, "loaded show", show or "unknown")
    return 0 if ok else 1


def _var(text: str, name: str) -> str | None:
    match = re.search(rf"\${name}\s*=\s*(.+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def cmd_cmd(cfg: Config, args: argparse.Namespace) -> int:
    command = " ".join(args.text)
    reason = risky_reason(command)
    if reason and not args.yes and not args.dry_run:
        if not _confirm(f"'{command}' {reason}. Send it?"):
            print("not sent")
            return 1
    with _connect_and_login(cfg, args.dry_run) as client:
        result = client.send(command)
        _print_result(result)
        return 0 if (result.ok or not result.sent) else 2


def cmd_shell(cfg: Config, args: argparse.Namespace) -> int:
    with _connect_and_login(cfg, args.dry_run) as client:
        print(f"Connected to {cfg.host}:{cfg.port} as '{client.user}'. Type 'exit' to leave.")
        while True:
            try:
                line = input(f"[{client.prompt or 'ma2'}]> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line.lower() in {"exit", "quit"}:
                break
            reason = risky_reason(line)
            if reason and not args.dry_run and not _confirm(f"This {reason}. Send it?"):
                print("not sent")
                continue
            try:
                _print_result(client.send(line))
            except MA2Error as exc:
                print(f"! {exc}", file=sys.stderr)
                if not client.connected and not args.dry_run:
                    return 1
    return 0


# -- entry point ---------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ma2kit", description="Toolkit for grandMA2 onPC.")
    parser.add_argument("--version", action="version", version=f"ma2kit {__version__}")
    parser.add_argument("--config", type=Path, help="path to config.toml")
    parser.add_argument("--dry-run", action="store_true", help="print commands instead of sending them")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("doctor", help="check that the console is reachable and the login works")

    p = sub.add_parser("cmd", help="send one command line and print the reply")
    p.add_argument("text", nargs="+", help='the command, e.g. "List Group"')
    p.add_argument("-y", "--yes", action="store_true", help="do not ask before risky commands")

    sub.add_parser("shell", help="interactive command line")
    return parser


COMMANDS = {"doctor": cmd_doctor, "cmd": cmd_cmd, "shell": cmd_shell}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    try:
        cfg = load_config(args.config)
        return COMMANDS[args.command](cfg, args)
    except (MA2Error, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
