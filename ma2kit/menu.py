"""Numbered terminal menu. Every entry runs the same code as the matching `ma2kit` subcommand."""
from __future__ import annotations

from collections.abc import Callable

Run = Callable[[list[str]], int]


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        return default
    return value or default


def _yes(prompt: str) -> bool:
    return _ask(f"{prompt} (y/N)").lower() in {"y", "yes"}


def _pause() -> None:
    try:
        input("\nPress Enter to return to the menu...")
    except EOFError:
        pass


def _groups(run: Run) -> None:
    start = _ask("First group number (empty = config default)")
    extra = ["--start", start] if start else []
    types = _ask("Only fixture types (comma list, empty = all)")
    extra += ["--types", types] if types else []
    if run(["groups", "auto", *extra]) == 0 and _yes("Create these groups now?"):
        run(["groups", "auto", *extra, "--apply"])


def _manager(run: Run, kind: str) -> None:
    """Submenu for "plugins" or "macros" (same commands; only plugins can be run from here)."""
    title = kind.capitalize()
    item = kind[:-1]
    while True:
        print(f"\n{title}")
        print("  1  List")
        print("  2  Install")
        print("  3  Update (load edited files)")
        print("  4  Remove")
        if kind == "plugins":
            print("  5  Run")
        print("  0  Back")
        choice = _ask("Choose")
        if choice == "1":
            run([kind, "list"])
        elif choice == "2":
            if names := _ask(f"{item.capitalize()} name(s), space separated").split():
                run([kind, "install", *names])
        elif choice == "3":
            run([kind, "update", *_ask(f"{item.capitalize()} name(s) (empty = all installed)").split()])
        elif choice == "4":
            names = _ask(f"{item.capitalize()} name(s) to remove").split()
            if names and _yes(f"Remove {', '.join(names)} from the show and delete their files?"):
                run([kind, "remove", *names])
        elif choice == "5" and kind == "plugins":
            if name := _ask("Plugin name or pool number"):
                run(["plugins", "run", name])
        elif choice in {"0", "q", ""}:
            return


def _batch(run: Run) -> None:
    path = _ask("Command file")
    if path and run(["batch", path]) == 0 and _yes("Send these commands now?"):
        run(["batch", path, "--apply"])


def run_menu(run: Run, status: Callable[[], str] | None = None) -> int:
    entries: list[tuple[str, Callable[[], object]]] = [
        ("Status check (connection, login, show)", lambda: run(["doctor"])),
        ("Show summary", lambda: run(["show", "summary"])),
        ("List fixtures", lambda: run(["show", "fixtures"] + (["--positions"] if _yes("Include stage positions?") else []))),
        ("Browse a pool", lambda: run(["show", "pool", _ask("Pool (Group, Effect, Macro, Layout, Sequence, Plugin...)", "Group")])),
        ("Group members", lambda: run(["show", "group", _ask("Group number", "1")])),
        ("Check the show (patch, names)", lambda: run(["show", "check"])),
        ("Find free pool slots", lambda: run(["show", "free", _ask("Pool", "Group"), "--count", _ask("How many in a row", "1")])),
        ("Auto groups", lambda: _groups(run)),
        ("Plugins", lambda: _manager(run, "plugins")),
        ("Macros", lambda: _manager(run, "macros")),
        ("Run a command file (batch)", lambda: _batch(run)),
        ("Backup the show", lambda: run(["backup"])),
        ("System monitor (Ctrl+C to stop)", lambda: run(["monitor", *(["--filter", f] if (f := _ask("Filter (regex, empty = all)")) else [])])),
        ("Command shell", lambda: run(["shell"])),
    ]
    while True:
        print("\nma2kit - grandMA2 toolkit")
        if status:
            print(f"  {status()}")
        for i, (label, _) in enumerate(entries, 1):
            print(f"  {i:>2}  {label}")
        print("   0  Quit")
        choice = _ask("Choose")
        if choice in {"0", "q", "quit", "exit"}:
            return 0
        if choice.isdigit() and 1 <= int(choice) <= len(entries):
            label, action = entries[int(choice) - 1]
            print(f"\n== {label}")
            try:
                action()
            except KeyboardInterrupt:
                print()
            if label not in {"Plugins", "Macros", "Command shell"}:
                _pause()
        else:
            print("Unknown choice.")
