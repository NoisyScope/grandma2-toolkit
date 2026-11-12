"""ma2kit command line."""
from __future__ import annotations

import argparse
import csv
import json
import re
import socket
import sys
from pathlib import Path

from . import __version__, backup, batch, checks, groups, monitor
from .client import (
    CommandResult,
    Dialog,
    LoginError,
    MA2Client,
    MA2Error,
    RemoteDisabledError,
    risky_reason,
)
from .config import Config, load_config
from .model import ShowModel, compress_ids
from .macros import MacroManager
from .plugins import PluginManager

EXPECTED_VERSION = "3.9.61"


# -- helpers ---------------------------------------------------------------
def _client(cfg: Config, dry_run: bool) -> MA2Client:
    return MA2Client(cfg.host, cfg.port, cfg.timeout, cfg.transcript, dry_run=dry_run)


class _Session:
    """One logged-in connection shared by all actions while the menu is open."""

    active = False
    client: MA2Client | None = None


def _connect_and_login(cfg: Config, dry_run: bool) -> MA2Client:
    if not cfg.password and not dry_run:
        raise MA2Error("no password configured: fill in [console] password in config.toml")
    if _Session.active and not dry_run:
        if _Session.client is None:
            client = _client(cfg, dry_run=False)
            client.connect()
            client.login(cfg.user, cfg.password)
            client.persistent = True
            _Session.client = client
        return _Session.client  # reconnects by itself if the console closed it
    client = _client(cfg, dry_run)
    client.connect()
    client.login(cfg.user, cfg.password)
    return client


def _session_status(cfg: Config) -> str:
    """Header line for the menu: connection, user and loaded show."""
    try:
        client = _connect_and_login(cfg, dry_run=False)
        model = ShowModel(client)
        show = model.var("SHOWFILE") or "?"
        guard = ""
        if cfg.allowed_shows:
            guard = " (may be changed)" if show in cfg.allowed_shows else " (read-only: not in allowed_shows)"
        return f"{cfg.host}:{cfg.port}  user {client.user}  show {show}{guard}"
    except (MA2Error, OSError) as exc:
        return f"not connected: {exc}"


def _model(cfg: Config) -> tuple[MA2Client, ShowModel]:
    client = _connect_and_login(cfg, dry_run=False)  # reading always talks to the console
    return client, ShowModel(client)


def _guard_write(cfg: Config, model: ShowModel) -> str:
    """Refuse to change a show that is not listed in [safety] allowed_shows (when the list is set)."""
    show = model.var("SHOWFILE") or "?"
    if cfg.allowed_shows and show not in cfg.allowed_shows:
        raise MA2Error(
            f"the loaded show '{show}' is not in [safety] allowed_shows in config.toml; refusing to change it"
        )
    return show


def _confirm(question: str) -> bool:
    try:
        return input(f"{question} [y/N] ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def _ask_dialog(dialog: Dialog) -> int | None:
    """Let the user answer a console confirmation dialog; Enter or anything invalid = Cancel."""
    print(f"Console asks: {dialog.question}")
    for number, label in dialog.options:
        print(f"  {number}: {label}")
    try:
        answer = input("Choice (Enter = Cancel): ").strip()
    except EOFError:
        return None
    return int(answer) if answer.isdigit() else None


def _dialog_handler():
    return _ask_dialog if sys.stdin.isatty() else None


def _print_result(result: CommandResult) -> None:
    if not result.sent:
        print(f"(dry-run) {result.command}")
        return
    if result.text:
        print(result.text)
    if result.late:
        print(result.late)
    # Error lines are already part of result.text; the exit code tells scripts the command failed.


def _table(headers: list[str], rows: list[list[object]]) -> str:
    cells = [[str(c) for c in r] for r in rows]
    widths = [max([len(h)] + [len(r[i]) for r in cells]) for i, h in enumerate(headers)]

    def line(r: list[str]) -> str:
        return "  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip()

    return "\n".join([line(headers), line(["-" * w for w in widths])] + [line(r) for r in cells])


# -- connection ------------------------------------------------------------
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

    try:
        with socket.create_connection((cfg.host, cfg.monitor_port), timeout=cfg.timeout):
            pass
        report(True, "system monitor", f"{cfg.host}:{cfg.monitor_port}")
    except OSError as exc:
        report(None, "system monitor", f"{cfg.host}:{cfg.monitor_port} not reachable ({exc})")

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

        model = ShowModel(client)
        version = model.var("VERSION")
        if version:
            report(version.startswith(EXPECTED_VERSION), "software version", version)
        else:
            report(None, "software version", "could not read $VERSION from ListVar")
        rights = model.var("USERRIGHTS")
        report(rights == "Admin" if rights else None, "user rights", rights or "unknown")
        show = model.var("SHOWFILE") or "unknown"
        if cfg.allowed_shows:
            allowed = show in cfg.allowed_shows
            report(allowed, "loaded show", f"{show} ({'may be changed' if allowed else 'NOT in allowed_shows: read-only'})")
        else:
            report(None, "loaded show", f"{show} (allowed_shows not set: any show may be changed)")
        plugin_path = model.var("PLUGINPATH")
        report(bool(plugin_path and Path(plugin_path).is_dir()) or None, "plugin folder", plugin_path or "unknown")
        if client.host in {"127.0.0.1", "localhost", "::1"}:
            stale = model.stale_temp_files()
            for path in stale:
                path.unlink(missing_ok=True)
            report(True, "temporary export files", f"removed {len(stale)} left over from an interrupted run" if stale else "none left over")
    return 0 if ok else 1


def cmd_cmd(cfg: Config, args: argparse.Namespace) -> int:
    command = " ".join(args.text)
    reason = risky_reason(command)
    if reason and not args.yes and not args.dry_run:
        if not _confirm(f"'{command}' {reason}. Send it?"):
            print("not sent")
            return 1
    with _connect_and_login(cfg, args.dry_run) as client:
        result = client.send(command, confirm=_dialog_handler())
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
                _print_result(client.send(line, confirm=_ask_dialog))
            except MA2Error as exc:
                print(f"! {exc}", file=sys.stderr)
                if not client.connected and not args.dry_run:
                    return 1
        if client.reconnects:
            print(f"(reconnected {client.reconnects} time(s) during this session)")
    return 0


def cmd_monitor(cfg: Config, args: argparse.Namespace) -> int:
    print(f"System monitor {cfg.host}:{cfg.monitor_port} (Ctrl+C to stop)")
    try:
        for line in monitor.stream(cfg.host, cfg.monitor_port, args.filter, cfg.timeout):
            print(line, flush=True)
    except KeyboardInterrupt:
        print()
    return 0


# -- show (read-only) ------------------------------------------------------
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
    if rows:
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


def cmd_show_check(cfg: Config, args: argparse.Namespace) -> int:
    client, model = _model(cfg)
    with client:
        issues = checks.run_all(model.fixtures(), model.fixture_types())
    if not issues:
        print("No problems found (patch overlaps, overflow past 512, unpatched fixtures, duplicate names).")
        return 0
    print(_table(["Severity", "Check", "Details"], [[i.severity, i.check, i.message] for i in issues]))
    errors = sum(i.severity == "error" for i in issues)
    print(f"\n{errors} error(s), {len(issues) - errors} warning(s)")
    return 2 if errors else 0


def cmd_show_free(cfg: Config, args: argparse.Namespace) -> int:
    client, model = _model(cfg)
    with client:
        used = model.used_numbers(args.pool)
    first = checks.free_numbers(used, args.start, args.count)
    if first is None:
        print(f"No {args.count} free {args.pool} slot(s) in a row from {args.start}.")
        return 1
    span = f"{first}" if args.count == 1 else f"{first}-{first + args.count - 1}"
    print(f"{args.pool} {span} is free ({len(used)} {args.pool} slot(s) used: {compress_ids(sorted(used)) or '-'})")
    return 0


# -- groups ------------------------------------------------------------------
def cmd_groups_auto(cfg: Config, args: argparse.Namespace) -> int:
    client, model = _model(cfg)
    with client:
        start = args.start if args.start is not None else cfg.group_start
        variants = tuple(v.strip().lower() for v in args.variants.split(",")) if args.variants else groups.DEFAULT_VARIANTS
        only = {t.strip().upper() for t in args.types.split(",")} if args.types else None
        plans = groups.plan_auto_groups(model.fixtures(), model.fixture_types(), start, variants, only)
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
        _guard_write(cfg, model)
        groups.apply(client, plans)
        created = {i.number: i.name for i in model.pool("Group")}
        missing = [p.no for p in plans if created.get(p.no) != p.name]
        if missing:
            print(f"\nWarning: not confirmed in the pool: {compress_ids(missing)}", file=sys.stderr)
            return 2
        print(f"\nCreated {len(plans)} groups: {plans[0].no}-{plans[-1].no}.")
    return 0


# -- plugins -----------------------------------------------------------------
def _plugins(cfg: Config) -> tuple[MA2Client, PluginManager]:
    client, model = _model(cfg)
    return client, PluginManager(model, cfg.plugin_start)


def cmd_plugins_list(cfg: Config, args: argparse.Namespace) -> int:
    client, manager = _plugins(cfg)
    with client:
        rows = manager.status()
        others = {n: s for n, s in manager.pool_slots().items() if n not in {r.name for r in rows}}
    print(_table(
        ["Plugin", "Installed", "Description"],
        [[r.name, f"Plugin {r.slot}" if r.slot is not None else ("files only" if r.files_installed else "no"), r.description] for r in rows],
    ))
    if others:
        print("\nOther plugins in this show: " + ", ".join(f"{s}: {n}" for n, s in sorted(others.items(), key=lambda x: x[1])))
    return 0


def cmd_plugins_install(cfg: Config, args: argparse.Namespace) -> int:
    client, manager = _plugins(cfg)
    with client:
        _guard_write(cfg, manager.model)
        for name in args.names:
            slot = manager.install(name, args.slot if len(args.names) == 1 else None)
            print(f"Installed {name} as Plugin {slot}")
    return 0


def cmd_plugins_update(cfg: Config, args: argparse.Namespace) -> int:
    client, manager = _plugins(cfg)
    with client:
        _guard_write(cfg, manager.model)
        names = manager.update(args.names or None)
    print(f"Updated (re-imported into their slots): {', '.join(names)}" if names else "No installed ma2kit plugins to update.")
    return 0


def cmd_plugins_remove(cfg: Config, args: argparse.Namespace) -> int:
    client, manager = _plugins(cfg)
    with client:
        _guard_write(cfg, manager.model)
        for name in args.names:
            slot = manager.remove(name)
            print(f"Removed {name}" + (f" (was Plugin {slot})" if slot is not None else " (files only)"))
    return 0


def cmd_plugins_run(cfg: Config, args: argparse.Namespace) -> int:
    client, manager = _plugins(cfg)
    with client:
        ok, output = manager.run(args.plugin, wait=args.wait)
    if output:
        print(output)
    if ok is None:
        print("(started; not waiting for it to finish)")
        return 0
    return 0 if ok else 2


# -- macros ------------------------------------------------------------------
def _macros(cfg: Config) -> tuple[MA2Client, MacroManager]:
    client, model = _model(cfg)
    return client, MacroManager(model, cfg.macro_start)


def cmd_macros_list(cfg: Config, args: argparse.Namespace) -> int:
    client, manager = _macros(cfg)
    with client:
        rows = manager.status()
    print(_table(
        ["Macro", "Lines", "Installed", "Description"],
        [[r.name, r.lines, f"Macro {r.slot}" if r.slot is not None else "no", r.description] for r in rows],
    ))
    return 0


def cmd_macros_install(cfg: Config, args: argparse.Namespace) -> int:
    client, manager = _macros(cfg)
    with client:
        _guard_write(cfg, manager.model)
        for name in args.names:
            slot = manager.install(name, args.slot if len(args.names) == 1 else None)
            print(f"Installed {name} as Macro {slot}")
    return 0


def cmd_macros_update(cfg: Config, args: argparse.Namespace) -> int:
    client, manager = _macros(cfg)
    with client:
        _guard_write(cfg, manager.model)
        names = manager.update(args.names or None)
    print(f"Updated (re-imported into their slots): {', '.join(names)}" if names else "No installed ma2kit macros to update.")
    return 0


def cmd_macros_remove(cfg: Config, args: argparse.Namespace) -> int:
    client, manager = _macros(cfg)
    with client:
        _guard_write(cfg, manager.model)
        for name in args.names:
            slot = manager.remove(name)
            print(f"Removed {name}" + (f" (was Macro {slot})" if slot is not None else " (files only)"))
    return 0


# -- batch -------------------------------------------------------------------
def cmd_batch(cfg: Config, args: argparse.Namespace) -> int:
    steps = batch.load(args.file)
    commands = [s for s in steps if s.command]
    if not commands:
        print("no commands in file")
        return 0
    print(_table(
        ["Line", "Command", "Note"],
        [[s.line_no, s.command if s.command else f"(wait {s.wait:g}s)", f"asks first: {s.risky}" if s.risky else ""] for s in steps],
    ))
    if not args.apply or args.dry_run:
        print(f"\n{len(commands)} command(s). Nothing was sent. Re-run with --apply to send them.")
        return 0
    risky = [s for s in commands if s.risky]
    if risky and not args.yes and not _confirm(f"{len(risky)} command(s) delete or replace data. Send the batch?"):
        print("not sent")
        return 1
    client, model = _model(cfg)
    with client:
        _guard_write(cfg, model)
        results = batch.run(client, steps, keep_going=args.keep_going, strict=args.strict)
    failed = [r for r in results if not r.ok]
    warned = [r for r in results if r.ok and r.warned]
    skipped = len(steps) - len(results)
    print(
        f"\n{len(results) - len(failed) - len(warned)} ok, {len(warned)} with warnings, {len(failed)} failed"
        + (f", {skipped} not run (stopped at first error)" if skipped else "")
    )
    return 0 if not failed else 2


# -- backup ------------------------------------------------------------------
def cmd_backup(cfg: Config, args: argparse.Namespace) -> int:
    client, model = _model(cfg)
    with client:
        target = backup.backup(model, cfg.backup_dir, cfg.backup_keep)
    print(f"Saved the show and copied it to {target}")
    return 0


# -- entry point ---------------------------------------------------------
def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ma2kit",
        description="Toolkit for grandMA2 onPC. Run without arguments for an interactive menu.",
    )
    parser.add_argument("--version", action="version", version=f"ma2kit {__version__}")
    parser.add_argument("--config", type=Path, help="path to config.toml")
    parser.add_argument("--dry-run", action="store_true", help="print commands instead of sending them")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("menu", help="interactive menu")
    p.set_defaults(func=lambda cfg, args: _run_menu(args))

    p = sub.add_parser("doctor", help="check connection, login, version, loaded show")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("cmd", help="send one command line and print the reply")
    p.add_argument("text", nargs="+", help='the command, e.g. "List Group"')
    p.add_argument("-y", "--yes", action="store_true", help="do not ask before risky commands")
    p.set_defaults(func=cmd_cmd)

    p = sub.add_parser("shell", help="interactive command line")
    p.set_defaults(func=cmd_shell)

    p = sub.add_parser("monitor", help="follow the console's system monitor (gma.echo output, command log)")
    p.add_argument("--filter", help="only lines matching this regular expression")
    p.set_defaults(func=cmd_monitor)

    p = sub.add_parser("backup", help="save the show and keep a timestamped copy of the show file")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("batch", help="run a text file of commands (preview unless --apply)")
    p.add_argument("file", help="text file, one command per line ('-' = stdin)")
    p.add_argument("--apply", action="store_true", help="actually send the commands")
    p.add_argument("--keep-going", action="store_true", help="continue after a failed command")
    p.add_argument("--strict", action="store_true", help="treat console warnings (e.g. NO OBJECTS FOUND) as errors")
    p.add_argument("-y", "--yes", action="store_true", help="do not ask before risky commands")
    p.set_defaults(func=cmd_batch)

    show = sub.add_parser("show", help="read the loaded show (read-only)").add_subparsers(dest="show_cmd", required=True)
    p = show.add_parser("summary", help="fixtures per type, patch span, pool usage")
    p.set_defaults(func=cmd_show_summary)
    p = show.add_parser("fixtures", help="list all fixtures")
    p.add_argument("--format", choices=["table", "json", "csv"], default="table")
    p.add_argument("--positions", action="store_true", help="include 3D stage positions (uses an XML export)")
    p.set_defaults(func=cmd_show_fixtures)
    p = show.add_parser("pool", help="list a pool, e.g. Group, Effect, Macro, Layout, Sequence, Plugin")
    p.add_argument("pool")
    p.set_defaults(func=cmd_show_pool)
    p = show.add_parser("group", help="members of a group, in order (uses an XML export)")
    p.add_argument("number", type=int)
    p.set_defaults(func=cmd_show_group)
    p = show.add_parser("check", help="find patch overlaps, overflow, unpatched fixtures, duplicate names")
    p.set_defaults(func=cmd_show_check)
    p = show.add_parser("free", help="first free slot(s) in a pool")
    p.add_argument("pool", help="e.g. Group, Macro, Effect, Sequence, Plugin, Layout")
    p.add_argument("--count", type=_positive_int, default=1, help="how many consecutive free slots are needed")
    p.add_argument("--start", type=_positive_int, default=1, help="search from this number")
    p.set_defaults(func=cmd_show_free)

    grp = sub.add_parser("groups", help="group utilities").add_subparsers(dest="groups_cmd", required=True)
    p = grp.add_parser("auto", help="create groups per fixture type (preview unless --apply)")
    p.add_argument("--start", type=_positive_int, help="first group pool number (default from config, 500)")
    p.add_argument("--variants", help=f"comma list from: {','.join(groups.VARIANTS)} (default: all)")
    p.add_argument("--types", help="only these fixture types (short name or type number), comma list")
    p.add_argument("--apply", action="store_true", help="actually create the groups")
    p.set_defaults(func=cmd_groups_auto)

    plg = sub.add_parser("plugins", help="manage this repo's Lua plugins in the show").add_subparsers(dest="plugins_cmd", required=True)
    p = plg.add_parser("list", help="repo plugins and where they are installed")
    p.set_defaults(func=cmd_plugins_list)
    p = plg.add_parser("install", help="copy plugin files to the console and import them")
    p.add_argument("names", nargs="+")
    p.add_argument("--slot", type=int, help="plugin pool number (single plugin only; default: first free from config)")
    p.set_defaults(func=cmd_plugins_install)
    p = plg.add_parser("update", help="re-copy installed plugins and import them again over their slots")
    p.add_argument("names", nargs="*", help="default: every installed ma2kit plugin")
    p.set_defaults(func=cmd_plugins_update)
    p = plg.add_parser("remove", help="delete plugins from the pool and their files")
    p.add_argument("names", nargs="+")
    p.set_defaults(func=cmd_plugins_remove)
    p = plg.add_parser("run", help="run a plugin by name or pool number and show its output")
    p.add_argument("plugin")
    p.add_argument("--wait", type=float, default=30.0, help="seconds to wait for a ma2kit plugin to finish (0 = don't wait)")
    p.set_defaults(func=cmd_plugins_run)

    mac = sub.add_parser("macros", help="manage this repo's text macros in the show").add_subparsers(dest="macros_cmd", required=True)
    p = mac.add_parser("list", help="repo macros and where they are installed")
    p.set_defaults(func=cmd_macros_list)
    p = mac.add_parser("install", help="build macro XML and import it")
    p.add_argument("names", nargs="+")
    p.add_argument("--slot", type=int, help="macro pool number (single macro only; default: first free from config)")
    p.set_defaults(func=cmd_macros_install)
    p = mac.add_parser("update", help="import edited macros again over their slots")
    p.add_argument("names", nargs="*", help="default: every installed ma2kit macro")
    p.set_defaults(func=cmd_macros_update)
    p = mac.add_parser("remove", help="delete macros from the pool and their files")
    p.add_argument("names", nargs="+")
    p.set_defaults(func=cmd_macros_remove)
    return parser


def _run_menu(args: argparse.Namespace) -> int:
    from .menu import run_menu

    base = (["--config", str(args.config)] if args.config else []) + (["--dry-run"] if args.dry_run else [])
    cfg = load_config(args.config)
    _Session.active = True
    try:
        return run_menu(lambda argv: main(base + argv), status=lambda: _session_status(cfg))
    finally:
        _Session.active = False
        if _Session.client is not None:
            _Session.client.close()
            _Session.client = None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # bad arguments: inside the menu, report and carry on instead of quitting
        if _Session.active:
            return int(exc.code or 0)
        raise
    if not getattr(args, "func", None):
        if sys.stdin.isatty() and sys.stdout.isatty():
            return _run_menu(args)
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
