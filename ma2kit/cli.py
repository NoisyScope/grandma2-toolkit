"""ma2kit command line."""
from __future__ import annotations

import argparse
import csv
import json
import re
import socket
import sys
from pathlib import Path

from . import __version__, groups
from .model import ShowModel, compress_ids
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


def _table(headers: list[str], rows: list[list[object]]) -> str:
    cells = [[str(c) for c in r] for r in rows]
    widths = [max([len(h)] + [len(r[i]) for r in cells]) for i, h in enumerate(headers)]
    line = lambda r: "  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip()
    return "\n".join([line(headers), line(["-" * w for w in widths])] + [line(r) for r in cells])


def _model(cfg: Config) -> tuple[MA2Client, ShowModel]:
    client = _connect_and_login(cfg, dry_run=False)  # reading always talks to the console
    return client, ShowModel(client)


def cmd_show_summary(cfg: Config, args: argparse.Namespace) -> int:
    client, model = _model(cfg)
    with client:
        s = model.summary()
    print(f"Show: {s.show}   software: {s.version}   user: {s.user}")
    universes = sorted({f.universe for f in s.fixtures if f.universe})
    print(f"Fixtures: {len(s.fixtures)} in {len({f.type_no for f in s.fixtures})} types, universes: {universes or '-'}")
    rows = []
    for t in s.types:
        fx = [f for f in s.fixtures if f.type_no == t.no]
        if not fx:
            continue
        patched = sorted((f.universe, f.address) for f in fx if f.universe)
        span = f"{patched[0][0]}.{patched[0][1]:03d} .. {patched[-1][0]}.{patched[-1][1]:03d}" if patched else "-"
        rows.append([t.no, f"{t.manufacturer} {t.long_name}", t.mode, t.footprint, len(fx), compress_ids([f.fid for f in fx]), span])
    print(_table(["Type", "Name", "Mode", "Ch", "Qty", "IDs", "Patch"], rows))
    print()
    print(_table(
        ["Pool", "Used", "Numbers"],
        [[name, len(items), compress_ids([n for i in items if (n := i.number) is not None]) or "-"] for name, items in s.pools.items()],
    ))
    return 0


def cmd_show_fixtures(cfg: Config, args: argparse.Namespace) -> int:
    client, model = _model(cfg)
    with client:
        fixtures = model.fixtures(positions=args.positions)
    records = [
        {
            "id": f.fid, "name": f.name, "type_no": f.type_no, "type": f.type_label,
            "universe": f.universe, "address": f.address,
            **({"x": f.position[0], "y": f.position[1], "z": f.position[2]} if args.positions and f.position else {}),
        }
        for f in fixtures
    ]
    if args.format == "json":
        print(json.dumps(records, indent=2))
    elif args.format == "csv":
        if records:
            writer = csv.DictWriter(sys.stdout, fieldnames=list(records[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(records)
    else:
        headers = ["ID", "Name", "Type", "Patch"] + (["X", "Y", "Z"] if args.positions else [])
        rows = [
            [f.fid, f.name, f"{f.type_no} {f.type_label}", f.patch]
            + ([f"{v:g}" for v in f.position] if args.positions and f.position else [])
            for f in fixtures
        ]
        print(_table(headers, rows))
    return 0


def cmd_show_pool(cfg: Config, args: argparse.Namespace) -> int:
    client, model = _model(cfg)
    with client:
        items = model.pool(args.pool)
    if not items:
        print(f"{args.pool}: empty")
        return 0
    print(_table(["No", "Name", "Info"], [[i.no, i.name, i.info] for i in items]))
    return 0


def cmd_show_group(cfg: Config, args: argparse.Namespace) -> int:
    client, model = _model(cfg)
    with client:
        members = model.group_members(args.number)
    print(f"Group {args.number}: {len(members)} fixtures, in order: {' '.join(map(str, members))}")
    return 0


def cmd_groups_auto(cfg: Config, args: argparse.Namespace) -> int:
    client, model = _model(cfg)
    with client:
        variants = tuple(v.strip().lower() for v in args.variants.split(",")) if args.variants else groups.DEFAULT_VARIANTS
        only = {t.strip().upper() for t in args.types.split(",")} if args.types else None
        plans = groups.plan_auto_groups(model.fixtures(), model.fixture_types(), args.start, variants, only)
        if not plans:
            print("nothing to create")
            return 0
        print(_table(
            ["Group", "Name", "Qty", "Fixtures (selection order)"],
            [[p.no, p.name, len(p.fixtures), " ".join(map(str, p.fixtures))] for p in plans],
        ))
        taken = groups.check_free(plans, model.used_numbers("Group"))
        if taken:
            print(f"\nRefusing: group slots already used: {compress_ids(taken)}. Choose another --start.", file=sys.stderr)
            return 1
        if not args.apply or args.dry_run:
            print("\nCommands that --apply would send:")
            for c in groups.commands_for(plans):
                print(f"  {c}")
            print("\nNothing was changed. Re-run with --apply to create these groups.")
            return 0
        groups.apply(client, plans)
        created = {i.number: i.name for i in model.pool("Group")}
        missing = [p.no for p in plans if created.get(p.no) != p.name]
        if missing:
            print(f"\nWarning: not confirmed in the pool: {compress_ids(missing)}", file=sys.stderr)
            return 2
        print(f"\nCreated {len(plans)} groups: {plans[0].no}-{plans[-1].no}.")
    return 0


# -- entry point ---------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ma2kit", description="Toolkit for grandMA2 onPC.")
    parser.add_argument("--version", action="version", version=f"ma2kit {__version__}")
    parser.add_argument("--config", type=Path, help="path to config.toml")
    parser.add_argument("--dry-run", action="store_true", help="print commands instead of sending them")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("doctor", help="check that the console is reachable and the login works")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("cmd", help="send one command line and print the reply")
    p.add_argument("text", nargs="+", help='the command, e.g. "List Group"')
    p.add_argument("-y", "--yes", action="store_true", help="do not ask before risky commands")
    p.set_defaults(func=cmd_cmd)

    p = sub.add_parser("shell", help="interactive command line")
    p.set_defaults(func=cmd_shell)

    show = sub.add_parser("show", help="read the loaded show (read-only)").add_subparsers(dest="show_cmd", required=True)
    p = show.add_parser("summary", help="fixtures per type, patch span, pool usage")
    p.set_defaults(func=cmd_show_summary)
    p = show.add_parser("fixtures", help="list all fixtures")
    p.add_argument("--format", choices=["table", "json", "csv"], default="table")
    p.add_argument("--positions", action="store_true", help="include 3D stage positions (uses an XML export)")
    p.set_defaults(func=cmd_show_fixtures)
    p = show.add_parser("pool", help="list a pool, e.g. Group, Effect, Macro, Layout, Sequence")
    p.add_argument("pool")
    p.set_defaults(func=cmd_show_pool)
    p = show.add_parser("group", help="members of a group, in order (uses an XML export)")
    p.add_argument("number", type=int)
    p.set_defaults(func=cmd_show_group)

    grp = sub.add_parser("groups", help="group utilities").add_subparsers(dest="groups_cmd", required=True)
    p = grp.add_parser("auto", help="create groups per fixture type (preview unless --apply)")
    p.add_argument("--start", type=int, default=500, help="first group pool number (default 500)")
    p.add_argument("--variants", help=f"comma list from: {','.join(groups.VARIANTS)} (default: all)")
    p.add_argument("--types", help="only these fixture types (short name or type number), comma list")
    p.add_argument("--apply", action="store_true", help="actually create the groups")
    p.set_defaults(func=cmd_groups_auto)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        cfg = load_config(args.config)
        return args.func(cfg, args)
    except (MA2Error, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
