"""Run a text file of console commands: preview first, stop on the first error.

File format:
    # comment lines and blank lines are ignored
    Fixture 1 Thru 10
    Store Group 600
    wait 1.5            # pause 1.5 s before the next command (a ma2kit directive, not sent)
    Label Group 600 "Front"

A trailing "# ..." after a command is NOT stripped, because "#" can be part of a command.
"""
from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .client import MA2Client, risky_reason

WAIT_RE = re.compile(r"^wait\s+(\d+(?:\.\d+)?)\s*(?:#.*)?$", re.IGNORECASE)


@dataclass
class Step:
    line_no: int
    command: str | None  # None for a wait step
    wait: float = 0.0

    @property
    def risky(self) -> str | None:
        return risky_reason(self.command) if self.command else None


@dataclass
class StepResult:
    step: Step
    ok: bool
    output: str
    warned: bool = False  # the console replied with a WARNING (e.g. no objects found: nothing done)


def parse(text: str) -> list[Step]:
    steps: list[Step] = []
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if m := WAIT_RE.match(line):
            steps.append(Step(no, None, float(m.group(1))))
        else:
            steps.append(Step(no, line))
    return steps


def load(path: Path | str) -> list[Step]:
    text = sys.stdin.read() if str(path) == "-" else Path(path).read_text(encoding="utf-8-sig")
    return parse(text)


def run(client: MA2Client, steps: list[Step], keep_going: bool = False, strict: bool = False, echo=print) -> list[StepResult]:
    """Send the steps in order. Dialogs are answered Cancel.

    Stops at the first error unless keep_going; with strict, a console WARNING counts as an error.
    """
    results: list[StepResult] = []

    def show_later() -> None:
        # Feedback that arrived after a step's reply (plugins, `Lua "..."`) belongs to that step.
        later = client.poll()
        if later:
            for out_line in later.splitlines():
                echo(f"        {out_line}")
            if results:
                prev = results[-1]
                prev.output = "\n".join(x for x in (prev.output, later) if x)

    for step in steps:
        show_later()
        if step.command is None:
            echo(f"  line {step.line_no}: wait {step.wait:g}s")
            if not client.dry_run:
                time.sleep(step.wait)
            results.append(StepResult(step, True, ""))
            continue
        result = client.send(step.command)
        output = "\n".join(x for x in (result.text, result.late) if x)
        warned = bool(result.warnings)
        ok = (result.ok or not result.sent) and not (strict and warned)
        results.append(StepResult(step, ok, output, warned))
        mark = "ERR" if not ok else ("WRN" if warned else "ok ")
        echo(f"  line {step.line_no}: [{mark}] {step.command}")
        if output.strip():
            for out_line in output.splitlines():
                echo(f"        {out_line}")
        if not ok and not keep_going:
            break
    if results:
        if not client.dry_run:
            time.sleep(0.3)  # let feedback from the last step arrive
        show_later()
    return results
