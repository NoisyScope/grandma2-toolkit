"""Load the local config.toml (git-ignored) that holds the console connection details."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Config:
    # [console]
    host: str = "127.0.0.1"
    port: int = 30000
    user: str = "toolkit"
    password: str = field(default="", repr=False)  # never shown in repr/logs
    timeout: float = 5.0
    # [log]
    transcript: Path | None = None
    # [safety]
    allowed_shows: list[str] = field(default_factory=list)  # empty = any show may be changed
    # [pools]
    group_start: int = 500
    plugin_start: int = 100
    macro_start: int = 500
    # [backup]
    backup_dir: Path = REPO_ROOT / "backups"
    backup_keep: int = 20
    # [monitor]
    monitor_port: int = 30001

    source: Path | None = None  # file the config was read from, None = defaults


def find_config(explicit: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(explicit)
    if env := os.environ.get("MA2KIT_CONFIG"):
        candidates.append(Path(env))
    candidates += [Path.cwd() / "config.toml", REPO_ROOT / "config.toml"]
    for path in candidates:
        if path.is_file():
            return path
    if explicit:
        raise FileNotFoundError(f"config file not found: {explicit}")
    return None


def load_config(explicit: Path | None = None) -> Config:
    path = find_config(explicit)
    cfg = Config()
    if path:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        base = path.parent
        console = data.get("console", {})
        cfg.host = str(console.get("host", cfg.host))
        cfg.port = int(console.get("port", cfg.port))
        cfg.user = str(console.get("user", cfg.user))
        cfg.password = str(console.get("password", cfg.password))
        cfg.timeout = float(console.get("timeout", cfg.timeout))
        if transcript := data.get("log", {}).get("transcript"):
            cfg.transcript = (base / transcript).resolve()
        shows = data.get("safety", {}).get("allowed_shows", [])
        cfg.allowed_shows = [shows] if isinstance(shows, str) else [str(s) for s in shows]
        pools = data.get("pools", {})
        cfg.group_start = int(pools.get("group_start", cfg.group_start))
        cfg.plugin_start = int(pools.get("plugin_start", cfg.plugin_start))
        cfg.macro_start = int(pools.get("macro_start", cfg.macro_start))
        backup = data.get("backup", {})
        if bdir := backup.get("dir"):
            cfg.backup_dir = (base / bdir).resolve()
        cfg.backup_keep = int(backup.get("keep", cfg.backup_keep))
        cfg.monitor_port = int(data.get("monitor", {}).get("port", cfg.monitor_port))
        cfg.source = path
    if env_pw := os.environ.get("MA2KIT_PASSWORD"):
        cfg.password = env_pw
    return cfg
