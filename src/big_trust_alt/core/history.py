"""Decision history: what was analyzed and chosen. File names only, no paths."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

MAX_ENTRIES = 500


def history_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "big-trust-alt" / "history.jsonl"


def record(name: str, sha256: str, file_format: str, app_id: str, action: str, result: str) -> None:
    from .settings import load_settings
    if not load_settings().get("keep_history", True):
        return
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    item = {"time": int(time.time()), "file": os.path.basename(name)[:200], "sha256": sha256,
            "format": file_format, "app": app_id, "action": action, "result": result}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    _trim(path)


def entries() -> list[dict]:
    try:
        with history_path().open(encoding="utf-8") as fh:
            items = []
            for line in fh:
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if isinstance(item, dict):
                    items.append(item)
            return items[::-1]
    except OSError:
        return []


def clear() -> None:
    try:
        history_path().unlink()
    except FileNotFoundError:
        pass


def _trim(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) > MAX_ENTRIES:
        from .settings import write_private_json  # noqa: F401  (same atomic pattern)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text("\n".join(lines[-MAX_ENTRIES:]) + "\n", encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
