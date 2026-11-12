"""Save the loaded show and keep timestamped copies of the show file.

Verified on 3.9.61: `SaveShow` replies `Show successfully saved as "<name>".` and writes
<MA data folder>/shows/<name>.show.gz, where the data folder is $PATH from ListVar.
"""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from .client import MA2Error
from .model import ShowModel

SAVED_RE = re.compile(r'Show successfully saved as "([^"]+)"')


def save_show(model: ShowModel) -> str:
    result = model.client.send("SaveShow", timeout=60)
    match = SAVED_RE.search(result.text)
    if not result.ok or not match:
        raise MA2Error(f"SaveShow failed: {'; '.join(result.errors) or result.text.strip() or 'no confirmation'}")
    return match.group(1)


def show_file(model: ShowModel, name: str) -> Path:
    ma_path = model.var("PATH")
    if not ma_path:
        raise MA2Error("could not read $PATH from the console")
    path = Path(ma_path) / "shows" / f"{name}.show.gz"
    if not path.is_file():
        raise MA2Error(f"saved show file not found: {path} (is onPC running on this PC?)")
    return path


def copy_with_rotation(source: Path, dest_dir: Path, name: str, keep: int, now: datetime | None = None) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    target = dest_dir / f"{name}_{stamp}.show.gz"
    shutil.copy2(source, target)
    copies = sorted(dest_dir.glob(f"{glob_escape(name)}_????????-??????.show.gz"))
    for old in copies[: max(0, len(copies) - keep)]:
        old.unlink()
    return target


def glob_escape(text: str) -> str:
    return re.sub(r"([\[\]*?])", r"[\1]", text)


def backup(model: ShowModel, dest_dir: Path, keep: int) -> Path:
    name = save_show(model)
    return copy_with_rotation(show_file(model, name), dest_dir, name, keep)
