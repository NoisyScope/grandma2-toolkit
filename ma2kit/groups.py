"""Generate useful groups from the patch and store them in empty group pool slots.

Verified on onPC 3.9.61: selecting with `Fixture a + b + c` keeps that order in the stored group,
`Store Group N` into an empty slot needs no confirmation, `Label Group N "name"` names it, and
`ClearSelection` replies Error #72 when nothing is selected (harmless). `Store` into an occupied slot
gives no error and no prompt, so slots must be checked for emptiness first.
"""
from __future__ import annotations

from dataclasses import dataclass

from .client import MA2Client, MA2Error
from .model import Fixture, FixtureType

VARIANTS = ("all", "odd", "even", "halves", "outin", "inout")
DEFAULT_VARIANTS = VARIANTS


@dataclass
class GroupPlan:
    no: int
    name: str
    fixtures: list[int]  # in selection order


def selection_command(ids: list[int]) -> str:
    """Build a `Fixture ...` selection that keeps the given order.

    Ascending runs of 3 or more consecutive IDs become "a Thru b" to keep the line short.
    """
    if not ids:
        raise ValueError("empty selection")
    parts: list[str] = []
    i = 0
    while i < len(ids):
        j = i
        while j + 1 < len(ids) and ids[j + 1] == ids[j] + 1:
            j += 1
        if j - i >= 2:
            parts.append(f"{ids[i]} Thru {ids[j]}")
            i = j + 1
        else:
            parts.append(str(ids[i]))
            i += 1
    return "Fixture " + " + ".join(parts)


def _variants(ids: list[int], wanted: tuple[str, ...]) -> list[tuple[str, list[int]]]:
    n = len(ids)
    out: list[tuple[str, list[int]]] = []
    if "all" in wanted:
        out.append(("ALL", ids))
    if n >= 2 and "odd" in wanted:
        out.append(("ODD", ids[0::2]))
    if n >= 2 and "even" in wanted:
        out.append(("EVEN", ids[1::2]))
    if n >= 4 and "halves" in wanted:
        half = (n + 1) // 2
        out.append(("1ST HALF", ids[:half]))
        out.append(("2ND HALF", ids[half:]))
    if n >= 3 and ("outin" in wanted or "inout" in wanted):
        outside_in = [ids[k // 2] if k % 2 == 0 else ids[n - 1 - k // 2] for k in range(n)]
        if "outin" in wanted:
            out.append(("OUT>IN", outside_in))
        if "inout" in wanted:
            out.append(("IN>OUT", list(reversed(outside_in))))
    return out


def plan_auto_groups(
    fixtures: list[Fixture],
    types: list[FixtureType],
    start: int,
    variants: tuple[str, ...] = DEFAULT_VARIANTS,
    only_types: set[str] | None = None,
    include_rig_all: bool = True,
) -> list[GroupPlan]:
    """Plan groups per fixture type (by fixture ID order), numbered from `start`."""
    unknown = set(variants) - set(VARIANTS)
    if unknown:
        raise ValueError(f"unknown variants: {', '.join(sorted(unknown))}")
    short = {t.no: (t.short_name or t.long_name or f"TYPE{t.no}") for t in types}
    by_type: dict[int, list[int]] = {}
    for f in sorted(fixtures, key=lambda f: f.fid):
        by_type.setdefault(f.type_no, []).append(f.fid)

    named: list[tuple[str, list[int]]] = []
    if include_rig_all and len(by_type) > 1 and not only_types:
        named.append(("ALL FIXTURES", sorted(f.fid for f in fixtures)))
    for type_no in sorted(by_type):
        label = short.get(type_no, f"TYPE{type_no}")
        if only_types and label.upper() not in only_types and str(type_no) not in only_types:
            continue
        for suffix, ids in _variants(by_type[type_no], variants):
            named.append((f"{label} {suffix}", ids))
    return [GroupPlan(start + i, name, ids) for i, (name, ids) in enumerate(named)]


def commands_for(plans: list[GroupPlan]) -> list[str]:
    cmds: list[str] = []
    for p in plans:
        if '"' in p.name:
            raise ValueError(f"group name contains a double quote: {p.name}")
        cmds += ["ClearSelection", selection_command(p.fixtures), f"Store Group {p.no}", f'Label Group {p.no} "{p.name}"']
    if plans:
        cmds.append("ClearSelection")
    return cmds


def check_free(plans: list[GroupPlan], used: set[int]) -> list[int]:
    """Return the planned numbers that are already occupied."""
    return sorted(p.no for p in plans if p.no in used)


def apply(client: MA2Client, plans: list[GroupPlan]) -> None:
    for cmd in commands_for(plans):
        result = client.send(cmd)
        if not result.sent or result.ok:
            continue
        code = result.error_code
        if cmd == "ClearSelection" and code and code[0] == 72:  # nothing was selected
            continue
        raise MA2Error(f"'{cmd}' failed: {'; '.join(result.errors)}")
