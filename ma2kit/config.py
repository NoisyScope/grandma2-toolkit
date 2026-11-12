"""Load the local config.toml (git-ignored) that holds the console connection details."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 30000
    user: str = "toolkit"
    password: str = field(default="", repr=False)  # never shown in repr/logs
    timeout: float = 5.0
    transcript: Path | None = None
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
        console = data.get("console", {})
        cfg.host = str(console.get("host", cfg.host))
        cfg.port = int(console.get("port", cfg.port))
        cfg.user = str(console.get("user", cfg.user))
        cfg.password = str(console.get("password", cfg.password))
        cfg.timeout = float(console.get("timeout", cfg.timeout))
        transcript = data.get("log", {}).get("transcript")
        if transcript:
            cfg.transcript = (path.parent / transcript).resolve()
        cfg.source = path
    if env_pw := os.environ.get("MA2KIT_PASSWORD"):
        cfg.password = env_pw
    return cfg
