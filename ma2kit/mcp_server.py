"""MCP server for grandMA2 onPC: lets an AI agent drive the console through its Telnet command line.

Run:  python -m ma2kit.mcp_server   (or the `ma2kit-mcp` script). It speaks MCP over stdio
(JSON-RPC 2.0, one message per line) and needs no packages beyond the standard library.

Everything sent to the console goes through MA2Client, so the transcript log, password masking,
dialog handling and reconnect behave as in the CLI.
"""
from __future__ import annotations

import html
import itertools
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .backup import backup
from .client import Dialog, LoginError, MA2Client, MA2Error, RemoteDisabledError, risky_reason
from .config import Config, load_config
from .mcp_guide import GUIDE, INSTRUCTIONS
from .model import ShowModel, parse_list

PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
READ_ONLY = ("list", "cd", "changedest", "cmdhelp", "help", "version", "export", "networkinfo")
REFUSED = ("login", "logout")
MAX_OUTPUT = 8000
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_PROP_RE = re.compile(r"^[A-Za-z][\w.]*$")
_counter = itertools.count(1)


class ToolError(Exception):
    """A refusal or failure reported to the agent as the tool's result."""


def first_word(command: str) -> str:
    return (command.strip().split(maxsplit=1) or [""])[0].lower()


def is_read_only(command: str) -> bool:
    word = first_word(command)
    return any(word.startswith(p) for p in READ_ONLY) or word == "li"


def clip(text: str, limit: int = MAX_OUTPUT) -> str:
    return text if len(text) <= limit else f"{text[:limit]}\n… ({len(text) - limit} more characters cut)"


def quote(value: Any) -> str:
    """Format a property value for `/name=value`."""
    if isinstance(value, bool):
        return '"On"' if value else '"Off"'
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if '"' in text or "\n" in text:
        raise ToolError('property values must not contain double quotes or line breaks')
    return f'"{text}"'


def cd_commands(path: list[str] | None) -> list[str]:
    steps = []
    for step in path or []:
        step = str(step).strip()
        if '"' in step:
            raise ToolError("path steps must not contain double quotes")
        steps.append(f"cd {step}" if step.isdigit() or step == ".." else f'cd "{step}"')
    return (["cd /"] + steps) if steps else []


def help_text(page: Path) -> str:
    raw = page.read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style|head).*?</\1>", "", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</(p|li|h\d|tr|div|pre)>", "\n", raw)
    raw = re.sub(r"(?i)</t[dh]>", " | ", raw)
    raw = html.unescape(re.sub(r"<[^>]+>", "", raw))
    lines: list[str] = []
    for line in raw.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return "\n".join(lines)


class Console:
    """One logged-in Telnet session, opened on first use and reopened after a failure."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.client: MA2Client | None = None
        self._hardware: tuple[float, dict] | None = None

    # -- connection ------------------------------------------------------
    def connect(self) -> MA2Client:
        if self.client is None:
            if not self.cfg.password:
                raise ToolError("no password configured: set [console] password in config.toml or MA2KIT_PASSWORD")
            client = MA2Client(self.cfg.host, self.cfg.port, self.cfg.timeout, self.cfg.transcript)
            try:
                client.connect()
                client.login(self.cfg.user, self.cfg.password)
            except Exception:
                client.close()
                raise
            self.client = client
        return self.client

    def drop(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None

    def model(self) -> ShowModel:
        return ShowModel(self.connect())

    def var(self, name: str) -> str:
        return self.model().var(name) or ""

    # -- probes ----------------------------------------------------------
    def hardware(self) -> dict:
        """Fader modules and granted universes; cached for a few seconds."""
        if self._hardware and time.monotonic() - self._hardware[0] < 10:
            return self._hardware[1]
        client = self.connect()
        text = client.send("ListFaderModules").text
        found = re.search(r"Found (\d+) internal and (\d+) external", text)
        modules = (int(found.group(1)) + int(found.group(2))) if found else 0
        rows = parse_list(client.send("List DmxUniverse", timeout=15).text)
        granted = [int(r.no) for r in rows if r["Granted"].lower() == "yes" and r.no.isdigit()]
        info = {"fader_modules": modules, "granted_universes": granted, "live_output": bool(modules or granted)}
        self._hardware = (time.monotonic(), info)
        return info

    def check_write(self, confirm_live: bool) -> None:
        show = self.var("SHOWFILE") or "?"
        allowed = self.cfg.allowed_shows
        if allowed and show not in allowed:
            raise ToolError(
                f"refused: the loaded show '{show}' is not in [safety] allowed_shows, so it may only be read"
            )
        if self.hardware()["live_output"] and not confirm_live:
            raise ToolError(
                "refused: DMX hardware is connected, so this can move or light real fixtures. "
                "Repeat with confirm_live=true only when a person at the rig has agreed."
            )

    # -- sending ---------------------------------------------------------
    def run(
        self,
        commands: list[str],
        keep_going: bool = False,
        answer_dialogs: str = "cancel",
        timeout: float | None = None,
    ) -> list[dict]:
        client = self.connect()

        def confirm(dialog: Dialog) -> int | None:
            if answer_dialogs == "cancel":
                return None
            if answer_dialogs == "default":
                return dialog.default
            return dialog.option(answer_dialogs)

        results: list[dict] = []
        moved = False
        try:
            for command in commands:
                moved = moved or first_word(command) in {"cd", "changedest"}
                result = client.send(command, timeout=timeout or 20, confirm=confirm)
                entry: dict[str, Any] = {"command": result.command, "ok": result.ok}
                if result.text.strip():
                    # keep leading spaces: List tables are aligned by column position
                    entry["output"] = clip(result.text.strip("\r\n").rstrip())
                if result.late.strip():
                    entry["later_output"] = clip(result.late.strip())
                if result.errors:
                    entry["errors"] = result.errors
                if result.warnings:
                    entry["warnings"] = result.warnings
                if result.dialog:
                    entry["dialog"] = {"question": result.dialog.question, "answered": result.answer}
                results.append(entry)
                if not result.ok and not keep_going:
                    break
            time.sleep(0.2)
            if results and (late := client.poll()):
                results[-1]["later_output"] = clip((results[-1].get("later_output", "") + "\n" + late).strip())
        except (OSError, MA2Error):
            self.drop()
            raise
        finally:
            if moved and self.client is not None:
                try:
                    self.client.send("cd /")
                except (OSError, MA2Error):
                    self.drop()
        return results


# -- tools ---------------------------------------------------------------------
class Tools:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.console = Console(cfg)

    # status ---------------------------------------------------------------
    def ma2_status(self) -> dict:
        cfg = self.cfg
        status: dict[str, Any] = {
            "server": f"ma2kit-mcp {__version__}",
            "console": f"{cfg.host}:{cfg.port}",
            "config_file": str(cfg.source) if cfg.source else "none found (defaults)",
            "user": cfg.user,
            "password_set": bool(cfg.password),
            "tools": {t["name"]: t["description"].split(". ")[0] for t in TOOLS},
            "guide_topics": {name: summary for name, (summary, _) in GUIDE.items()},
        }
        try:
            socket.create_connection((cfg.host, cfg.port), timeout=2).close()
            status["reachable"] = True
        except OSError as exc:
            status.update(reachable=False, connected=False, problem=f"cannot reach the console: {exc}",
                          fix="Start grandMA2 onPC and check [console] host and port in config.toml.")
            return status
        try:
            self.console.drop()  # probe with a fresh login
            model = self.console.model()
            variables = model.variables(refresh=True)
        except RemoteDisabledError:
            status.update(connected=False, problem="Telnet is disabled on the console",
                          fix="In onPC: Setup > Console > Global Settings > Telnet = Login Enabled.")
            return status
        except LoginError as exc:
            status.update(connected=False, problem=f"login failed: {exc}",
                          fix="Check the MA user name and password in config.toml (case-sensitive).")
            return status
        except (ToolError, MA2Error, OSError) as exc:
            status.update(connected=False, problem=str(exc))
            return status
        show = variables.get("SHOWFILE", "?")
        allowed = cfg.allowed_shows
        status.update(
            connected=True,
            logged_in_as=variables.get("USER"),
            user_rights=variables.get("USERRIGHTS"),
            software_version=variables.get("VERSION"),
            host=f"{variables.get('HOSTTYPE', '?')} / {variables.get('HOSTSUBTYPE', '?')}",
            session=variables.get("HOSTSTATUS"),
            show=show,
            show_may_be_changed=(show in allowed) if allowed else True,
            show_guard=f"allowed_shows = {allowed}" if allowed else "not set: any loaded show may be changed",
            selected_fixtures=variables.get("SELECTEDFIXTURESCOUNT"),
            ma_data_folder=variables.get("PATH"),
        )
        try:
            hardware = self.console.hardware()
            status["hardware"] = hardware
            status["output_note"] = (
                "DMX hardware is connected: changes need confirm_live=true and a person at the rig."
                if hardware["live_output"]
                else "No DMX hardware: nothing reaches real fixtures; results show in the Stage view only."
            )
        except (MA2Error, OSError) as exc:
            status["hardware"] = f"probe failed: {exc}"
        status["official_help"] = (
            f"{len(list(self._help_dir().glob('*.html')))} pages" if self._help_dir().is_dir() else "not found"
        )
        return status

    # commands -------------------------------------------------------------
    def ma2_command(
        self,
        commands: list[str] | str,
        keep_going: bool = False,
        allow_destructive: bool = False,
        confirm_live: bool = False,
        answer_dialogs: str = "cancel",
        timeout: float | None = None,
    ) -> dict:
        lines = [commands] if isinstance(commands, str) else list(commands)
        lines = [ln.strip() for ln in lines if ln and ln.strip()]
        if not lines:
            raise ToolError("no commands given")
        for line in lines:
            if "\n" in line or "\r" in line:
                raise ToolError("one command line per list item")
            if first_word(line) in REFUSED or first_word(line).startswith("logi"):
                raise ToolError("Login/Logout are not sent: the server logs in with the configured MA user")
            if (reason := risky_reason(line)) and not allow_destructive:
                raise ToolError(f"refused: '{line}' {reason}. Repeat with allow_destructive=true if intended.")
        if not all(is_read_only(line) for line in lines):
            self.console.check_write(confirm_live)
        results = self.console.run(lines, keep_going, answer_dialogs, timeout)
        failed = [r["command"] for r in results if not r["ok"]]
        return {
            "sent": len(results),
            "of": len(lines),
            "failed": failed,
            "stopped_early": len(results) < len(lines),
            "results": results,
        }

    def ma2_list(self, what: str = "", path: list[str] | None = None, limit: int = 200) -> dict:
        command = f"List {what}".strip()
        if not is_read_only(command):
            raise ToolError("ma2_list only lists")
        results = self.console.run(cd_commands(path) + [command], timeout=20)
        last = results[-1]
        if not last["ok"]:
            return {"ok": False, "command": last["command"], "errors": last.get("errors", []),
                    "hint": "Error #14 often means the object is not reachable from this place in the tree."}
        text = last.get("output", "")
        rows = parse_list(text)
        out: dict[str, Any] = {"ok": True, "command": command, "path": path or [], "count": len(rows)}
        if rows:
            out["rows"] = [{"object": f"{r.cls} {r.no}", **r.cols} for r in rows[:limit]]
            if len(rows) > limit:
                out["note"] = f"first {limit} of {len(rows)} rows; raise limit or narrow the list"
        elif text and "NO OBJECTS FOUND" not in text:
            out["raw"] = text  # not a table (for example executors print key=value lines)
        return out

    def ma2_set(
        self,
        path: list[str],
        target: str,
        properties: dict[str, Any],
        confirm_live: bool = False,
    ) -> dict:
        if not properties:
            raise ToolError("no properties given")
        target = str(target).strip()
        if not target or '"' in target or "/" in target:
            raise ToolError('target is the object number(s) at that place, e.g. "2" or "1 Thru 4"')
        for name in properties:
            if not _PROP_RE.match(name):
                raise ToolError(f"bad property name: {name!r} (use the List column name without spaces)")
        self.console.check_write(confirm_live)
        options = " ".join(f"/{name}={quote(value)}" for name, value in properties.items())
        commands = cd_commands(path) + [f"Assign {target} {options}", f"List {target}"]
        results = self.console.run(commands, timeout=20)
        assign = next((r for r in results if r["command"].startswith("Assign ")), None)
        out: dict[str, Any] = {"ok": bool(assign and assign["ok"]), "command": commands[-2], "path": path}
        if not assign:
            out["errors"] = results[-1].get("errors", ["could not reach the path"])
            out["failed_at"] = results[-1]["command"]
        elif not assign["ok"]:
            out["errors"] = assign.get("errors", [])
        else:
            listing = results[-1]
            rows = parse_list(listing.get("output", ""))
            out["now"] = [{"object": f"{r.cls} {r.no}", **r.cols} for r in rows] or listing.get("output", "")
            out["note"] = "Check 'now': the console accepts some assignments without changing anything."
        return out

    # XML ------------------------------------------------------------------
    def _need_local(self) -> Path:
        if self.cfg.host not in _LOCAL_HOSTS:
            raise ToolError("reading or writing files needs onPC running on the same PC as this server")
        root = self.console.var("PATH")
        if not root:
            raise ToolError("could not read $PATH from the console")
        return Path(root)

    def ma2_export(self, object: str, path: list[str] | None = None, max_chars: int = 20000) -> dict:
        root = self._need_local()
        if '"' in object:
            raise ToolError("object must not contain double quotes")
        name = f"ma2kit_tmp_mcp_{os.getpid()}_{next(_counter)}"
        results = self.console.run(cd_commands(path) + [f'Export {object} "{name}"'], timeout=30)
        last = results[-1]
        if not last["ok"]:
            return {"ok": False, "command": last["command"], "errors": last.get("errors", [])}
        files: list[Path] = []
        deadline = time.monotonic() + 5
        while not files and time.monotonic() < deadline:
            files = list(root.glob(f"{name}.xml")) + list(root.glob(f"*/{name}.xml"))
            if not files:
                time.sleep(0.1)
        if not files:
            raise ToolError(f"the console reported success but {name}.xml was not found under {root}")
        try:
            xml = files[0].read_text(encoding="utf-8-sig", errors="replace")
        finally:
            for f in files:
                f.unlink(missing_ok=True)
        return {"ok": True, "object": object, "folder": files[0].parent.name, "characters": len(xml),
                "xml": clip(xml, max_chars)}

    def ma2_import(
        self,
        destination: str = "",
        xml: str = "",
        file: str = "",
        path: list[str] | None = None,
        answer_dialogs: str = "cancel",
        confirm_live: bool = False,
    ) -> dict:
        if bool(xml) == bool(file):
            raise ToolError("give either xml (the content) or file (a name in the console's own folders)")
        if '"' in destination or '"' in file:
            raise ToolError("destination and file must not contain double quotes")
        self.console.check_write(confirm_live)
        at = f" At {destination}" if destination else ""
        folder: Path | None = None
        try:
            if xml:
                self._need_local()
                folder = Path(tempfile.mkdtemp(prefix="ma2kit_mcp_"))
                name = f"ma2kit_tmp_mcp_{next(_counter)}"
                (folder / f"{name}.xml").write_text(xml, encoding="utf-8", newline="\n")
                command = f'Import "{name}"{at} /path="{folder.as_posix()}"'
            else:
                command = f'Import "{file}"{at}'
            results = self.console.run(cd_commands(path) + [command], answer_dialogs=answer_dialogs, timeout=30)
        finally:
            if folder:
                shutil.rmtree(folder, ignore_errors=True)
        last = results[-1]
        out = {"ok": last["ok"], "command": last["command"], "output": last.get("output", "")}
        if last.get("errors"):
            out["errors"] = last["errors"]
        if last.get("dialog"):
            out["dialog"] = last["dialog"]
        return out

    # Lua ------------------------------------------------------------------
    def ma2_lua(self, code: str, timeout: float = 10, confirm_live: bool = False) -> dict:
        self._need_local()
        self.console.check_write(confirm_live)
        folder = Path(tempfile.mkdtemp(prefix="ma2kit_mcp_"))
        user, wrap, out = folder / "user.lua", folder / "wrap.lua", folder / "out.txt"
        try:
            user.write_text(code, encoding="utf-8", newline="\n")
            wrap.write_text(
                "local out = {}\n"
                "local function emit(...)\n"
                "  local t = {}\n"
                "  for i = 1, select('#', ...) do t[#t + 1] = tostring((select(i, ...))) end\n"
                "  out[#out + 1] = table.concat(t, '\\t')\n"
                "end\n"
                "local env = setmetatable({print = emit}, {__index = _G})\n"
                f"local chunk, err = loadfile([[{user.as_posix()}]], 't', env)\n"
                "if not chunk then emit('SYNTAX ERROR: ' .. tostring(err)) else\n"
                "  local res = table.pack(pcall(chunk))\n"
                "  if not res[1] then emit('ERROR: ' .. tostring(res[2])) else\n"
                "    for i = 2, res.n do emit('return: ' .. tostring(res[i])) end\n"
                "  end\n"
                "end\n"
                f"local f = assert(io.open([[{out.as_posix()}]], 'w'))\n"
                "f:write(table.concat(out, '\\n'))\n"
                "f:close()\n",
                encoding="utf-8",
                newline="\n",
            )
            results = self.console.run([f"Lua \"dofile([[{wrap.as_posix()}]])\""], timeout=timeout + 5)
            deadline = time.monotonic() + timeout
            while not out.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            if not out.exists():
                return {"ok": False, "problem": f"no result after {timeout}s (still running, or it failed)",
                        "console": results[-1]}
            time.sleep(0.05)
            text = out.read_text(encoding="utf-8", errors="replace")
            failed = text.startswith(("SYNTAX ERROR:", "ERROR:")) or "\nERROR: " in text
            return {"ok": not failed, "output": clip(text)}
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    # knowledge ------------------------------------------------------------
    def _help_dir(self) -> Path:
        roots: list[Path] = []
        if self.console.client is not None:
            try:
                if root := self.console.var("PATH"):
                    roots.append(Path(root))
            except (ToolError, MA2Error, OSError):
                pass
        base = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "MA Lighting Technologies" / "grandma"
        if base.is_dir():
            roots += sorted(base.glob("gma2_V_*"), reverse=True)
        for root in roots:
            if (root / "lang" / "en" / "help").is_dir():
                return root / "lang" / "en" / "help"
        return base / "missing"

    def ma2_help(self, query: str = "", page: str = "", max_chars: int = 6000) -> dict:
        folder = self._help_dir()
        if not folder.is_dir():
            raise ToolError("MA's help pages were not found (expected <MA data folder>/lang/en/help)")
        pages = {p.stem.removeprefix("key_"): p for p in folder.glob("*.html")}
        if page:
            key = page.removeprefix("key_").removesuffix(".html")
            if key not in pages:
                raise ToolError(f"no help page named '{page}'")
            return {"page": key, "text": clip(help_text(pages[key]), max_chars)}
        words = [w for w in re.split(r"[^a-z0-9]+", query.lower()) if w]
        if not words:
            return {"pages": len(pages), "keywords": sorted(k.removeprefix("keyword_") for k in pages
                                                            if k.startswith("keyword_")),
                    "hint": "ma2_help(query='store') for a keyword, or any words to search all pages"}
        scored: list[tuple[int, str]] = []
        joined = "".join(words)
        for key, file in pages.items():
            score = 0
            if key == f"keyword_{joined}":
                score += 1000
            score += sum(40 for w in words if w in key.split("_"))
            score += sum(10 for w in words if w in key)
            if score < 1000:
                body = help_text(file).lower()
                score += sum(min(body.count(w), 15) for w in words)
                if not all(w in body or w in key for w in words):
                    score = score // 4
            if score > 0:
                scored.append((score, key))
        scored.sort(reverse=True)
        if not scored:
            return {"matches": [], "hint": "no page mentions that; try one keyword"}
        best = scored[0][1]
        return {"matches": [key for _, key in scored[:10]], "page": best,
                "text": clip(help_text(pages[best]), max_chars),
                "hint": "ma2_help(page='<name>') opens another match"}

    def ma2_guide(self, topic: str = "") -> dict:
        if not topic:
            return {"topics": {name: summary for name, (summary, _) in GUIDE.items()},
                    "marks": "[v] verified on onPC 3.9.61 over Telnet · [doc] from MA's help, not tried · [x] failed here"}
        key = topic.strip().lower()
        if key not in GUIDE:
            raise ToolError(f"unknown topic '{topic}'. Topics: {', '.join(GUIDE)}")
        return {"topic": key, "summary": GUIDE[key][0], "recipe": GUIDE[key][1]}

    # high level -----------------------------------------------------------
    def ma2_patch(
        self,
        layer: str,
        count: int,
        first_fixture_id: int,
        fixture_type: int = 0,
        library_file: str = "",
        name: str = "",
        universe: int = 0,
        address: int = 0,
        positions: list[list[float]] | None = None,
        rotations: list[list[float]] | None = None,
        confirm_live: bool = False,
    ) -> dict:
        if count < 1 or count > 500:
            raise ToolError("count must be 1..500")
        if bool(fixture_type) == bool(library_file):
            raise ToolError("give either fixture_type (a number already in the show) or library_file")
        if any('"' in s for s in (layer, name, library_file)) or not layer.strip():
            raise ToolError("layer is required; names must not contain double quotes")
        for label, coords in (("positions", positions), ("rotations", rotations)):
            if coords is not None and (len(coords) != count or any(len(c) != 3 for c in coords)):
                raise ToolError(f"{label} needs one [x, y, z] per fixture ({count})")
        if bool(universe) != bool(address):
            raise ToolError("give both universe and address, or neither (unpatched)")
        self.console.check_write(confirm_live)
        model = self.console.model()
        last_id = first_fixture_id + count - 1
        existing = model.fixtures()
        taken = sorted(f.fid for f in existing if first_fixture_id <= f.fid <= last_id)
        if taken:
            raise ToolError(f"fixture IDs already in use: {taken}")
        log: list[dict] = []

        def step(commands: list[str], **kw: Any) -> list[dict]:
            results = self.console.run(commands, **kw)
            log.extend({k: r[k] for k in ("command", "ok", "errors") if k in r} for r in results)
            if not results[-1]["ok"]:
                raise ToolError(json.dumps({"problem": "patching stopped at a failed command", "log": log}))
            return results

        types_path = ["cd /", 'cd "EditSetup"', 'cd "FixtureTypes"']
        if library_file:
            before = {r.no for r in parse_list(step(types_path + ["List"])[-1].get("output", ""))}
            step(types_path + [f'Import "{library_file}"'], timeout=30)
        rows = parse_list(step(types_path + ["List"])[-1].get("output", ""))
        if library_file:
            new = [r for r in rows if r.no not in before]
            if not new:
                raise ToolError(f"'{library_file}' was not imported; check the name with the command ListLibrary")
            fixture_type = int(new[-1].no)
        chosen = next((r for r in rows if r.no == str(fixture_type)), None)
        if chosen is None:
            raise ToolError(f"fixture type {fixture_type} is not in the show; see ma2_list path=['EditSetup','FixtureTypes']")
        footprint = int(chosen["DMXFootprint"] or 0)
        layers_path = ["cd /", 'cd "EditSetup"', 'cd "Layers"']
        try:
            if universe:
                end = address + count * footprint - 1
                if address < 1 or end > 512:
                    raise ToolError(f"{count} x {footprint} channels from {universe}.{address:03d} ends at {end}: past 512")
                sizes = {t.no: t.footprint for t in model.fixture_types()}
                clashes = [
                    f.fid for f in existing
                    if f.universe == universe and f.address
                    and f.address <= end and f.address + max(sizes.get(f.type_no, 1), 1) - 1 >= address
                ]
                if clashes:
                    raise ToolError(f"addresses {universe}.{address:03d}-{end:03d} overlap fixtures {sorted(clashes)}")
            layers = parse_list(step(layers_path + ["List"])[-1].get("output", ""))
            if any(r["Name"] == layer for r in layers):
                raise ToolError(f"a layer named '{layer}' already exists; choose a new layer name")
        except ToolError:
            if library_file:  # nothing was patched: take the just-imported fixture type out again
                self.console.run(types_path + [f"Delete {fixture_type} /nc"])
            raise
        layer_no = max([int(r.no) for r in layers if r.no.isdigit()] + [0]) + 1
        span = "1" if count == 1 else f"1 Thru {count}"
        commands = layers_path + [
            f'Store {layer_no} "{layer}"',
            f"cd {layer_no}",
            f"Store {span}",
            f"Assign {span} /FixId={first_fixture_id}",
            f"Assign FixtureType {fixture_type} At {span}",
        ]
        for i in range(count):
            options = []
            if name:
                options.append(f'/Name="{name} {i + 1}"' if count > 1 else f'/Name="{name}"')
            if options:
                commands.append(f"Assign {i + 1} {' '.join(options)}")
            sub = []
            if universe:
                sub.append(f'/Patch="{universe}.{address + i * footprint:03d}"')
            if positions:
                sub += [f"/Pos{axis}={positions[i][k]}" for k, axis in enumerate("XYZ")]
            if rotations:
                sub += [f"/Rot{axis}={rotations[i][k]}" for k, axis in enumerate("XYZ")]
            if sub:
                commands += [f"cd {i + 1}", f"Assign 1 {' '.join(sub)}", "cd .."]
        step(commands)
        listing = self.ma2_list(f"Fixture {first_fixture_id} Thru {last_id}" if count > 1 else f"Fixture {first_fixture_id}")
        return {"ok": True, "layer": {"number": layer_no, "name": layer}, "fixture_type": fixture_type,
                "footprint": footprint, "commands_sent": len(log), "fixtures": listing.get("rows", []),
                "note": "Positions are stored on the subfixture; the Stage view shows them."}

    def ma2_backup(self) -> dict:
        path = backup(self.console.model(), self.cfg.backup_dir, self.cfg.backup_keep)
        return {"ok": True, "saved_copy": str(path), "kept_per_show": self.cfg.backup_keep}


# -- tool catalogue ------------------------------------------------------------
def _schema(properties: dict[str, dict], required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}


_PATH = {"type": "array", "items": {"type": "string"},
         "description": 'Steps into the object tree from the root, by name or number, e.g. ["EditSetup","Layers","2"]'}
_LIVE = {"type": "boolean", "description": "Required when DMX hardware is connected (see ma2_status): a person at the rig has agreed"}
_DIALOG = {"type": "string", "description": 'How to answer a console dialog: "cancel" (default), "default" (the highlighted option, e.g. Ok or Overwrite), or an option label such as "Insert"'}

TOOLS: list[dict] = [
    {"name": "ma2_status",
     "description": "Probe the connection to grandMA2 onPC and list what this server can do. Reports: reachable, "
                    "Telnet enabled, login, software version, loaded show and whether it may be changed, DMX "
                    "hardware (live output), every tool, and the guide topics. Call this first.",
     "inputSchema": _schema({}), "annotations": {"readOnlyHint": True}},
    {"name": "ma2_command",
     "description": "Send command lines to the console exactly as typed at its command line, in one session. "
                    "Returns each command's output, errors and warnings; stops at the first error unless "
                    "keep_going. `cd` state lasts for the call, then returns to the root. Anything Telnet allows "
                    "can be sent; see ma2_guide and ma2_help for syntax.",
     "inputSchema": _schema({
         "commands": {"type": "array", "items": {"type": "string"}, "description": "Command lines, in order"},
         "keep_going": {"type": "boolean", "description": "Continue after a failed command"},
         "allow_destructive": {"type": "boolean", "description": "Needed for Delete, NewShow, LoadShow, Shutdown, Reboot, Restart and anything with /nc"},
         "confirm_live": _LIVE, "answer_dialogs": _DIALOG,
         "timeout": {"type": "number", "description": "Seconds to wait per command (default 20)"},
     }, ["commands"])},
    {"name": "ma2_list",
     "description": "List objects as structured rows: a pool (`what`=\"Group\", \"Preset 4.*\", \"Fixture 1 Thru 10\", "
                    "\"Sequence\", \"Macro 1.5.*\") or the children of a place in the object tree (`path`). With neither, "
                    "lists the top level of the tree. Read-only.",
     "inputSchema": _schema({
         "what": {"type": "string", "description": "What follows the List keyword; empty lists the current place"},
         "path": _PATH, "limit": {"type": "integer", "description": "Maximum rows (default 200)"},
     }), "annotations": {"readOnlyHint": True}},
    {"name": "ma2_set",
     "description": "Set properties of an object from inside the object tree (the form that works over Telnet): "
                    "goes to `path`, sends `Assign <target> /Property=value …`, lists the object again and returns "
                    "to the root. Property names are the List column names without spaces.",
     "inputSchema": _schema({
         "path": _PATH,
         "target": {"type": "string", "description": 'Object number(s) at that place, e.g. "2" or "1 Thru 4"'},
         "properties": {"type": "object", "description": 'e.g. {"CMD": "ClearAll", "Wait": 0.5} or {"PanOffset": 3.5}'},
         "confirm_live": _LIVE,
     }, ["path", "target", "properties"])},
    {"name": "ma2_export",
     "description": "Read an object's full content as XML (values the List table does not show): presets, groups, "
                    "sequences with cue values, layouts, macros, effects, timecode shows, fixtures, patch layers, "
                    "executors. The temporary export file is deleted. Read-only.",
     "inputSchema": _schema({
         "object": {"type": "string", "description": 'e.g. "Preset 2.1", "Sequence 5", "Layout 3"; with path, a number at that place'},
         "path": _PATH, "max_chars": {"type": "integer", "description": "Cut the XML after this many characters (default 20000)"},
     }, ["object"]), "annotations": {"readOnlyHint": True}},
    {"name": "ma2_import",
     "description": "Import XML into the show: either `xml` content you provide (macros, effects, layouts, …) or a "
                    "`file` name from the console's own folders (for a fixture type: file=\"generic@dimmer@00\" with "
                    "path [\"EditSetup\",\"FixtureTypes\"]). Importing over an occupied slot opens a dialog.",
     "inputSchema": _schema({
         "destination": {"type": "string", "description": 'Where it goes, e.g. "Macro 900"; empty = the place given by path'},
         "xml": {"type": "string", "description": "XML content in grandMA2 export format"},
         "file": {"type": "string", "description": "File name in the console's folder for that object type, without extension"},
         "path": _PATH, "answer_dialogs": _DIALOG, "confirm_live": _LIVE,
     })},
    {"name": "ma2_lua",
     "description": "Run Lua 5.3 code inside the console and return what it prints or returns. Use it to read "
                    "object properties with gma.show.getobj / gma.show.property (see ma2_guide topic 'lua'). "
                    "Code can also change the show through gma.cmd.",
     "inputSchema": _schema({
         "code": {"type": "string", "description": "Lua source; print(...) and return values are captured"},
         "timeout": {"type": "number", "description": "Seconds to wait for the result (default 10)"},
         "confirm_live": _LIVE,
     }, ["code"])},
    {"name": "ma2_help",
     "description": "Search MA Lighting's official grandMA2 help installed with onPC (829 pages, one per command "
                    "keyword). query=\"store\" opens that keyword's page; other words search all pages; no arguments "
                    "lists every keyword. Works without a console connection.",
     "inputSchema": _schema({
         "query": {"type": "string", "description": "A keyword or search words"},
         "page": {"type": "string", "description": "Open this page name from an earlier result"},
         "max_chars": {"type": "integer", "description": "Cut the page after this many characters (default 6000)"},
     }), "annotations": {"readOnlyHint": True}},
    {"name": "ma2_guide",
     "description": "Command recipes checked on onPC 3.9.61 for: basics, patch, position, presets, sequences, "
                    "executors, macros, layouts, views, timecode, effects, lua, safety. Each line is marked as "
                    "verified, documented only, or failed. No arguments lists the topics.",
     "inputSchema": _schema({"topic": {"type": "string", "description": "A topic name"}}),
     "annotations": {"readOnlyHint": True}},
    {"name": "ma2_patch",
     "description": "Create fixtures in a new patch layer in one step: optionally import the fixture type from the "
                    "library, create the layer and fixtures, number them, patch consecutive DMX addresses and set "
                    "3D positions. Checks that the IDs are free and the addresses do not overlap or pass 512.",
     "inputSchema": _schema({
         "layer": {"type": "string", "description": "Name of the new layer"},
         "count": {"type": "integer", "description": "How many fixtures"},
         "first_fixture_id": {"type": "integer", "description": "Fixture ID of the first one; the rest count up"},
         "fixture_type": {"type": "integer", "description": "Number of a fixture type already in the show"},
         "library_file": {"type": "string", "description": 'Or a library file to import first, e.g. "generic@dimmer@00"'},
         "name": {"type": "string", "description": 'Fixture name; numbered "name 1", "name 2", …'},
         "universe": {"type": "integer", "description": "DMX universe of the first fixture (omit to leave unpatched)"},
         "address": {"type": "integer", "description": "DMX address of the first fixture"},
         "positions": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}, "description": "One [x, y, z] in metres per fixture"},
         "rotations": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}, "description": "One [x, y, z] in degrees per fixture"},
         "confirm_live": _LIVE,
     }, ["layer", "count", "first_fixture_id"])},
    {"name": "ma2_backup",
     "description": "Save the show (SaveShow) and keep a timestamped copy of the show file in the toolkit's backup "
                    "folder. Do this before patch changes or bulk edits.",
     "inputSchema": _schema({})},
]


# -- JSON-RPC over stdio -------------------------------------------------------
class Server:
    def __init__(self, cfg: Config) -> None:
        self.tools = Tools(cfg)

    def handle(self, message: dict) -> dict | None:
        method, msg_id = message.get("method"), message.get("id")
        if msg_id is None:  # notification
            return None
        try:
            result = self.dispatch(method, message.get("params") or {})
        except KeyError as exc:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"unknown: {exc}"}}
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def dispatch(self, method: str | None, params: dict) -> dict:
        if method == "initialize":
            wanted = params.get("protocolVersion")
            return {
                "protocolVersion": wanted if wanted in PROTOCOLS else PROTOCOLS[0],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ma2kit-mcp", "title": "grandMA2 onPC", "version": __version__},
                "instructions": INSTRUCTIONS,
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": TOOLS}
        if method == "tools/call":
            return self.call(params.get("name", ""), params.get("arguments") or {})
        raise KeyError(method)

    def call(self, name: str, arguments: dict) -> dict:
        func: Callable[..., dict] | None = getattr(self.tools, name, None) if name.startswith("ma2_") else None
        if func is None:
            return _reply(f"unknown tool '{name}'", error=True)
        try:
            return _reply(func(**arguments))
        except TypeError as exc:
            return _reply(f"bad arguments for {name}: {exc}", error=True)
        except ToolError as exc:
            return _reply(str(exc), error=True)
        except (MA2Error, OSError, ValueError) as exc:
            self.tools.console.drop()
            return _reply(f"console error: {exc}. Run ma2_status to check the connection.", error=True)


def _reply(result: Any, error: bool = False) -> dict:
    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=1)
    return {"content": [{"type": "text", "text": text}], "isError": error}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    config = Path(args[args.index("--config") + 1]) if "--config" in args else None
    server = Server(load_config(config))
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    sys.stdout = sys.stderr  # nothing but protocol messages may reach stdout
    for raw in stdin:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            reply: dict | None = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            reply = server.handle(message) if isinstance(message, dict) else None
        if reply is not None:
            stdout.write((json.dumps(reply, ensure_ascii=False) + "\n").encode("utf-8"))
            stdout.flush()
    server.tools.console.drop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
