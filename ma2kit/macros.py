"""Install, update and remove macros written as plain text files in the repo (macros/<name>.txt).

Source format:
    # description: One line shown by `ma2kit macros list`
    # other comment lines and blank lines are ignored
    ClearAll
    Fixture 1 Thru 10
    wait 0.5            # becomes the delay of the line above (MA's macro "Wait" column)
    At 100

The macro XML mirrors MA's own macros/predefined.xml: <Macro name=..><Macroline index=.. delay=..><text>.
Import works like plugins (see plugins.py): files go to <MA data folder>/macros/ma2kit/ and are imported
with `Import "ma2kit/<name>.xml" At Macro N`; updating imports again over the same slot.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from .client import MA2Error
from .config import REPO_ROOT
from .model import ShowModel

SOURCE_DIR = REPO_ROOT / "macros"
INSTALL_SUBDIR = "ma2kit"
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_ .+-]{0,30}$")
DESC_RE = re.compile(r"^#\s*description:\s*(.+)$", re.MULTILINE)
WAIT_RE = re.compile(r"^wait\s+(\d+(?:\.\d+)?)\s*(?:#.*)?$", re.IGNORECASE)
IMPORTED_RE = re.compile(r"(\d+) object\(s\) from .* imported")

XML_HEAD = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<MA xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://schemas.malighting.de/grandma2/xml/MA" '
    'xsi:schemaLocation="http://schemas.malighting.de/grandma2/xml/MA http://schemas.malighting.de/grandma2/xml/3.9.61/MA.xsd" '
    'major_vers="3" minor_vers="9" stream_vers="61">\n'
    '\t<Info datetime="2026-01-01T00:00:00" showfile="ma2kit" />\n'
)


@dataclass
class MacroLine:
    text: str
    delay: float = 0.0


@dataclass
class SourceMacro:
    name: str
    path: Path
    description: str
    lines: list[MacroLine]


@dataclass
class MacroStatus:
    name: str
    description: str
    lines: int
    slot: int | None


def parse_source(name: str, text: str, path: Path | None = None) -> SourceMacro:
    lines: list[MacroLine] = []
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if m := WAIT_RE.match(line):
            if not lines:
                raise MA2Error(f"{name}: line {no}: 'wait' needs a command before it")
            lines[-1].delay += float(m.group(1))
            continue
        lines.append(MacroLine(line))
    if not lines:
        raise MA2Error(f"{name}: no macro lines")
    desc = DESC_RE.search(text)
    return SourceMacro(name, path or Path(f"{name}.txt"), desc.group(1).strip() if desc else "", lines)


def source_macros(directory: Path = SOURCE_DIR) -> list[SourceMacro]:
    out = []
    for path in sorted(directory.glob("*.txt")):
        if NAME_RE.match(path.stem):
            out.append(parse_source(path.stem, path.read_text(encoding="utf-8-sig"), path))
    return out


def get_source(name: str, directory: Path = SOURCE_DIR) -> SourceMacro:
    for macro in source_macros(directory):
        if macro.name == name:
            return macro
    raise MA2Error(f"no macro source macros/{name}.txt")


def macro_xml(macro: SourceMacro) -> str:
    parts = [XML_HEAD, f"\t<Macro index=\"0\" name={quoteattr(macro.name)}>\n"]
    for i, line in enumerate(macro.lines):
        delay = f' delay="{line.delay:g}"' if line.delay else ""
        parts.append(f'\t\t<Macroline index="{i}"{delay}>\n\t\t\t<text>{escape(line.text, {chr(34): "&quot;"})}</text>\n\t\t</Macroline>\n')
    parts.append("\t</Macro>\n</MA>\n")
    return "".join(parts)


class MacroManager:
    def __init__(self, model: ShowModel, macro_start: int = 500, source_dir: Path = SOURCE_DIR):
        self.model = model
        self.client = model.client
        self.macro_start = macro_start
        self.source_dir = source_dir

    def install_dir(self) -> Path:
        path = self.model.var("PATH")
        if not path:
            raise MA2Error("could not read $PATH from the console")
        return Path(path) / "macros" / INSTALL_SUBDIR

    def pool_slots(self) -> dict[str, int]:
        return {item.name: n for item in self.model.pool("Macro") if (n := item.number) is not None}

    def status(self) -> list[MacroStatus]:
        slots = self.pool_slots()
        return [MacroStatus(m.name, m.description, len(m.lines), slots.get(m.name)) for m in source_macros(self.source_dir)]

    def _write(self, name: str) -> None:
        macro = get_source(name, self.source_dir)
        target = self.install_dir()
        target.mkdir(parents=True, exist_ok=True)
        (target / f"{name}.xml").write_text(macro_xml(macro), encoding="utf-8", newline="\n")

    def _import(self, name: str, slot: int, overwrite: bool) -> None:
        result = self.client.send(
            f'Import "{INSTALL_SUBDIR}/{name}.xml" At Macro {slot}',
            timeout=20,
            confirm=(lambda d: d.option("Overwrite")) if overwrite else None,
        )
        if not result.ok or not IMPORTED_RE.search(result.text):
            raise MA2Error(f"import of macro {name} failed: {'; '.join(result.errors) or result.text.strip()}")

    def install(self, name: str, slot: int | None = None) -> int:
        slots = self.pool_slots()
        if name in slots:
            raise MA2Error(f"{name} is already installed as Macro {slots[name]}; use update")
        used = self.model.used_numbers("Macro")
        if slot is None:
            slot = self.macro_start
            while slot in used:
                slot += 1
        elif slot in used:
            raise MA2Error(f"Macro {slot} is already used")
        self._write(name)
        self._import(name, slot, overwrite=False)
        if self.pool_slots().get(name) != slot:
            raise MA2Error(f"{name} not found at Macro {slot} after import")
        return slot

    def update(self, names: list[str] | None = None) -> list[str]:
        slots = self.pool_slots()
        names = names or [m.name for m in source_macros(self.source_dir) if m.name in slots]
        missing = [n for n in names if n not in slots]
        if missing:
            raise MA2Error(f"not installed (use install): {', '.join(missing)}")
        for name in names:
            self._write(name)
            self._import(name, slots[name], overwrite=True)
        return names

    def remove(self, name: str) -> int | None:
        slot = self.pool_slots().get(name)
        if slot is not None:
            result = self.client.send(f"Delete Macro {slot} /nc")
            if not result.ok:
                raise MA2Error(f"Delete Macro {slot} failed: {'; '.join(result.errors)}")
        target = self.install_dir()
        (target / f"{name}.xml").unlink(missing_ok=True)
        if target.is_dir() and not any(target.iterdir()):
            target.rmdir()
        return slot
