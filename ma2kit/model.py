"""Read-only view of the loaded show: fixtures, fixture types, pools and group members.

Sources (all verified on onPC 3.9.61):
  * `List <Pool>` replies are fixed-width tables. The header row's column starts line up with the
    values, and each row starts with "<Class> <number>" in the space before the first column.
  * An empty pool replies "WARNING, NO OBJECTS FOUND FOR LIST".
  * `Export <object> "<name>"` writes <name>.xml under the MA data folder ($PATH): groups land in
    importexport/, fixtures in fixtures/. Group XML lists <Subfixture fix_id=".."> in selection order;
    fixture XML carries the absolute DMX address and the 3D stage position, which `List Fixture` does not.
"""
from __future__ import annotations

import itertools
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .client import MA2Client, MA2Error

NO_OBJECTS = "NO OBJECTS FOUND FOR LIST"
_ROW_PREFIX_RE = re.compile(r"^(\S+)\s+(\S+)")
_PATCH_RE = re.compile(r"^(\d+)\.(\d+)$")
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_tmp_counter = itertools.count(1)


# -- List output parsing ---------------------------------------------------
@dataclass
class ListRow:
    cls: str  # e.g. "Fixture", "Group"
    no: str  # pool number as printed, e.g. "100" or "6.1"
    cols: dict[str, str]

    def __getitem__(self, key: str) -> str:
        return self.cols.get(key, "")


def parse_list(text: str) -> list[ListRow]:
    """Parse the fixed-width table MA prints for `List <something>`."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines or any(NO_OBJECTS in ln for ln in lines[:2]):
        return []
    header = lines[0]
    starts = [(m.start(), m.group()) for m in re.finditer(r"\S+", header)]
    if not starts:
        return []
    rows: list[ListRow] = []
    for line in lines[1:]:
        prefix = _ROW_PREFIX_RE.match(line[: starts[0][0]])
        if not prefix:
            continue
        cols: dict[str, str] = {}
        for i, (start, name) in enumerate(starts):
            end = starts[i + 1][0] if i + 1 < len(starts) else None
            cols[name] = line[start:end].strip()
        rows.append(ListRow(prefix.group(1), prefix.group(2), cols))
    return rows


def parse_patch(text: str) -> tuple[int, int] | None:
    match = _PATCH_RE.match(text.strip())
    return (int(match.group(1)), int(match.group(2))) if match else None


def compress_ids(ids: list[int]) -> str:
    """[1,2,3,5] -> "1-3, 5" (for display)."""
    parts: list[str] = []
    for _, run in itertools.groupby(enumerate(sorted(ids)), lambda p: p[1] - p[0]):
        values = [v for _, v in run]
        parts.append(str(values[0]) if len(values) == 1 else f"{values[0]}-{values[-1]}")
    return ", ".join(parts)


# -- data classes ----------------------------------------------------------
@dataclass
class FixtureType:
    no: int
    long_name: str
    short_name: str
    manufacturer: str
    footprint: int
    mode: str
    used: int


@dataclass
class Fixture:
    fid: int
    name: str
    type_no: int
    type_label: str  # as printed by List Fixture, e.g. "BEAM 8R + RING 24CH"
    universe: int | None
    address: int | None
    position: tuple[float, float, float] | None = None  # filled by ShowModel.fixtures(positions=True)

    @property
    def patch(self) -> str:
        return f"{self.universe}.{self.address:03d}" if self.universe and self.address else "-"


@dataclass
class PoolItem:
    pool: str
    no: str
    name: str
    info: str = ""

    @property
    def number(self) -> int | None:
        return int(self.no) if self.no.isdigit() else None


@dataclass
class ShowSummary:
    show: str | None
    version: str | None
    user: str | None
    types: list[FixtureType]
    fixtures: list[Fixture]
    pools: dict[str, list[PoolItem]] = field(default_factory=dict)


# -- XML exports -----------------------------------------------------------
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(elem: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in elem.iter() if _local(c.tag) == name]


def parse_group_xml(root: ET.Element) -> list[int]:
    return [int(s.get("fix_id")) for s in _children(root, "Subfixture") if s.get("fix_id")]


def parse_fixtures_xml(root: ET.Element) -> dict[int, dict]:
    """fixture id -> {"address": absolute DMX address or None, "position": (x, y, z) or None}."""
    out: dict[int, dict] = {}
    for fx in _children(root, "Fixture"):
        fid = fx.get("fixture_id")
        if fid is None:
            continue
        address = position = None
        addr = next(iter(_children(fx, "Address")), None)
        if addr is not None and (addr.text or "").strip().isdigit():
            address = int(addr.text.strip())
        loc = next(iter(_children(fx, "Location")), None)
        if loc is not None:
            position = tuple(float(loc.get(axis, 0)) for axis in ("x", "y", "z"))
        out[int(fid)] = {"address": address, "position": position}
    return out


# -- the model -------------------------------------------------------------
class ShowModel:
    def __init__(self, client: MA2Client) -> None:
        self.client = client
        self._vars: dict[str, str] | None = None

    # system variables
    def variables(self, refresh: bool = False) -> dict[str, str]:
        if self._vars is None or refresh:
            text = self._list("ListVar")
            self._vars = {
                m.group(1).upper(): m.group(2).strip()
                for m in re.finditer(r"\$(\w+)\s*=\s*(.*)", text)
            }
        return self._vars

    def var(self, name: str) -> str | None:
        return self.variables().get(name.upper())

    # pools
    def pool(self, name: str) -> list[PoolItem]:
        rows = parse_list(self._list(f"List {name}"))
        return [PoolItem(r.cls, r.no, r["Name"], r["Info"]) for r in rows]

    def used_numbers(self, name: str) -> set[int]:
        return {n for item in self.pool(name) if (n := item.number) is not None}

    def fixture_types(self) -> list[FixtureType]:
        out = []
        for r in parse_list(self._list("List FixtureType")):
            out.append(
                FixtureType(
                    no=int(r.no),
                    long_name=r["LongName"],
                    short_name=r["ShortName"],
                    manufacturer=r["Manufacturer"],
                    footprint=_int(r["DMXFootprint"]),
                    mode=r["Mode"],
                    used=_int(r["Used"]),
                )
            )
        return out

    def fixtures(self, positions: bool = False) -> list[Fixture]:
        out = []
        for r in parse_list(self._list("List Fixture")):
            type_no, _, type_label = r["FixtureType"].partition(" ")
            patch = parse_patch(r["Patch"])
            out.append(
                Fixture(
                    fid=_int(r["FixId"]) or _int(r.no),
                    name=r["Name"],
                    type_no=_int(type_no),
                    type_label=type_label,
                    universe=patch[0] if patch else None,
                    address=patch[1] if patch else None,
                )
            )
        if positions and out:
            ids = [f.fid for f in out]
            data = parse_fixtures_xml(self.export_xml(f"Fixture {min(ids)} Thru {max(ids)}"))
            for f in out:
                f.position = data.get(f.fid, {}).get("position")
        return out

    def group_members(self, number: int) -> list[int]:
        return parse_group_xml(self.export_xml(f"Group {number}"))

    def summary(self) -> ShowSummary:
        pools = {name: self.pool(name) for name in ("Group", "Effect", "Sequence", "Macro", "Layout", "Plugin", "MAtricks")}
        return ShowSummary(
            show=self.var("SHOWFILE"),
            version=self.var("VERSION"),
            user=self.var("USER"),
            types=self.fixture_types(),
            fixtures=self.fixtures(),
            pools=pools,
        )

    # exports
    def export_xml(self, obj: str) -> ET.Element:
        """Export an object to XML, read the file, delete it, and return the parsed root."""
        if self.client.dry_run:
            raise MA2Error("reading exports is not possible in dry-run mode")
        if self.client.host not in _LOCAL_HOSTS:
            raise MA2Error("XML export reading needs onPC running on this PC")
        ma_path = self.var("PATH")
        if not ma_path:
            raise MA2Error("could not read $PATH from the console")
        name = f"ma2kit_tmp_{os.getpid()}_{next(_tmp_counter)}"
        result = self.client.send(f'Export {obj} "{name}"', timeout=20)
        if not result.ok:
            raise MA2Error(f"Export {obj} failed: {'; '.join(result.errors)}")
        root_dir = Path(ma_path)
        deadline = time.monotonic() + 5
        while True:
            files = list(root_dir.glob(f"{name}.xml")) + list(root_dir.glob(f"*/{name}.xml"))
            if files or time.monotonic() > deadline:
                break
            time.sleep(0.1)
        if not files:
            raise MA2Error(f"export file {name}.xml not found under {root_dir}")
        try:
            return ET.parse(files[0]).getroot()
        finally:
            for f in files:
                f.unlink(missing_ok=True)

    def _list(self, command: str) -> str:
        result = self.client.send(command, timeout=15)
        if not result.ok:
            raise MA2Error(f"{command} failed: {'; '.join(result.errors)}")
        return result.text


def _int(text: str) -> int:
    text = text.strip()
    return int(text) if text.lstrip("-").isdigit() else 0
