"""User settings (~/.config/big-trust-alt/settings.json), written atomically."""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS = {"prefer_flatpak": False, "show_aur": True, "keep_history": True,
            "mime_backup": {}}


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "big-trust-alt"


def load_settings() -> dict:
    path = config_dir() / "settings.json"
    data = dict(DEFAULTS)
    try:
        with path.open(encoding="utf-8") as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            data.update({k: v for k, v in stored.items() if k in DEFAULTS and type(v) is type(DEFAULTS[k])})
    except (OSError, ValueError):
        pass
    return data


def save_settings(data: dict) -> None:
    write_private_json(config_dir() / "settings.json", data)


def write_private_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
