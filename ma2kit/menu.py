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


def _plugins(run: Run) -> None:
    while True:
        print("\nPlugins")
        print("  1  List")
        print("  2  Install")
        print("  3  Update (load edited code)")
        print("  4  Run")
        print("  5  Remove")
        print("  0  Back")
        choice = _ask("Choose")
        if choice == "1":
            run(["plugins", "list"])
        elif choice == "2":
            if names := _ask("Plugin name(s), space separated").split():
                run(["plugins", "install", *names])
        elif choice == "3":
            run(["plugins", "update", *_ask("Plugin name(s) (empty = all installed)").split()])
        elif choice == "4":
            if name := _ask("Plugin name or pool number"):
                run(["plugins", "run", name])
        elif choice == "5":
            names = _ask("Plugin name(s) to remove").split()
            if names and _yes(f"Remove {', '.join(names)} from the show and delete their files?"):
                run(["plugins", "remove", *names])
        elif choice in {"0", "q", ""}:
            return


def run_menu(run: Run) -> int:
    entries: list[tuple[str, Callable[[], object]]] = [
        ("Status check (connection, login, show)", lambda: run(["doctor"])),
        ("Show summary", lambda: run(["show", "summary"])),
        ("List fixtures", lambda: run(["show", "fixtures"] + (["--positions"] if _yes("Include stage positions?") else []))),
        ("Browse a pool", lambda: run(["show", "pool", _ask("Pool (Group, Effect, Macro, Layout, Sequence, Plugin...)", "Group")])),
        ("Group members", lambda: run(["show", "group", _ask("Group number", "1")])),
        ("Auto groups", lambda: _groups(run)),
        ("Plugins", lambda: _plugins(run)),
        ("Backup the show", lambda: run(["backup"])),
        ("System monitor (Ctrl+C to stop)", lambda: run(["monitor", *(["--filter", f] if (f := _ask("Filter (regex, empty = all)")) else [])])),
        ("Command shell", lambda: run(["shell"])),
    ]
    while True:
        print("\nma2kit - grandMA2 toolkit")
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
            if label not in {"Plugins", "Command shell"}:
                _pause()
        else:
            print("Unknown choice.")
