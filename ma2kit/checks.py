"""Generic show checks: patch problems and naming slips that are easy to miss on the console."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .model import Fixture, FixtureType, compress_ids

UNIVERSE_SIZE = 512


@dataclass
class Issue:
    severity: str  # "error" or "warning"
    check: str
    message: str


def check_patch(fixtures: list[Fixture], types: list[FixtureType]) -> list[Issue]:
    footprint = {t.no: t.footprint for t in types}
    issues: list[Issue] = []

    unpatched = [f.fid for f in fixtures if f.universe is None]
    if unpatched:
        issues.append(Issue("warning", "unpatched", f"{len(unpatched)} fixture(s) not patched: {compress_ids(unpatched)}"))

    by_universe: dict[int, list[tuple[int, int, Fixture]]] = defaultdict(list)
    for f in fixtures:
        if f.universe is None or f.address is None:
            continue
        size = footprint.get(f.type_no, 0)
        if size <= 0:
            continue
        end = f.address + size - 1
        if end > UNIVERSE_SIZE:
            issues.append(Issue(
                "error", "overflow",
                f"fixture {f.fid} at {f.patch} needs {size} channels and runs past {UNIVERSE_SIZE} (to {end})",
            ))
        by_universe[f.universe].append((f.address, end, f))

    for universe, spans in sorted(by_universe.items()):
        spans.sort(key=lambda s: (s[0], s[2].fid))
        for i, (start, end, fx) in enumerate(spans):
            for other_start, other_end, other in spans[i + 1 :]:
                if other_start > end:
                    break
                issues.append(Issue(
                    "error", "overlap",
                    f"universe {universe}: fixture {fx.fid} ({start}-{end}) overlaps fixture {other.fid} ({other_start}-{other_end})",
                ))
    return issues


def check_names(fixtures: list[Fixture]) -> list[Issue]:
    by_name: dict[str, list[int]] = defaultdict(list)
    for f in fixtures:
        if f.name:
            by_name[f.name].append(f.fid)
    return [
        Issue("warning", "duplicate-name", f'name "{name}" is used by fixtures {compress_ids(ids)}')
        for name, ids in sorted(by_name.items())
        if len(ids) > 1
    ]


def run_all(fixtures: list[Fixture], types: list[FixtureType]) -> list[Issue]:
    return check_patch(fixtures, types) + check_names(fixtures)


def free_numbers(used: set[int], start: int = 1, count: int = 1, limit: int = 10000) -> int | None:
    """First number >= start where `count` consecutive numbers are unused."""
    n = start
    while n + count - 1 <= limit:
        clash = next((k for k in range(n + count - 1, n - 1, -1) if k in used), None)
        if clash is None:
            return n
        n = clash + 1
    return None
