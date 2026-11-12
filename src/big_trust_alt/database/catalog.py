"""Load the application catalog: packaged data plus an optional local overlay.

The overlay (~/.local/share/big-trust-alt/catalog/*.json) lets the catalog
be fixed or extended without reinstalling the program. Every file is
validated; a file that fails validation is skipped as a whole, so the last
valid data always wins (that is the rollback).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .schema import SchemaError, validate_catalog, validate_document

MAX_FILE = 4 << 20


def data_dirs() -> list[Path]:
    """Where packaged data lives: env override, source tree, then /usr/share."""
    dirs = []
    if os.environ.get("BIG_TRUST_ALT_DATA"):
        dirs.append(Path(os.environ["BIG_TRUST_ALT_DATA"]))
    dirs.append(Path(__file__).resolve().parents[3] / "data")
    dirs.append(Path("/usr/share/big-trust-alt"))
    return [d for d in dirs if (d / "app-db" / "catalog").is_dir()]


def overlay_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "big-trust-alt" / "catalog"


@dataclass
class Catalog:
    entries: dict[str, dict] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def get(self, entry_id: str) -> dict | None:
        return self.entries.get(entry_id)

    def __len__(self) -> int:
        return len(self.entries)

    def search(self, text: str, limit: int = 20) -> list[dict]:
        """Name/alias/vendor search for the 'find an alternative' page."""
        from .normalize import fold

        query = fold(text)
        if not query:
            return []
        scored = []
        for entry in self.entries.values():
            names = [entry["name"], *entry.get("aliases", ())]
            folded = [fold(n) for n in names]
            vendor = fold(entry.get("vendor", ""))
            if any(f == query for f in folded):
                score = 0
            elif any(f.startswith(query) for f in folded):
                score = 1
            elif any(query in f for f in folded):
                score = 2
            elif query in vendor or all(t in " ".join(folded) for t in query.split()):
                score = 3
            else:
                continue
            scored.append((score, entry["name"].lower(), entry))
        scored.sort(key=lambda item: item[:2])
        return [entry for *_, entry in scored[:limit]]


def _read(path: Path) -> list[dict]:
    if path.stat().st_size > MAX_FILE:
        raise SchemaError(f"{path.name}: file too large")
    with path.open(encoding="utf-8") as fh:
        return validate_document(json.load(fh), path.name)


def load(extra_dirs: list[Path] | None = None, use_overlay: bool = True) -> Catalog:
    catalog = Catalog()
    base = data_dirs()
    if not base and not extra_dirs:
        catalog.problems.append("no catalog data found")
        return catalog
    dirs = [base[0] / "app-db" / "catalog"] if base else []
    dirs += extra_dirs or []
    entries: dict[str, dict] = {}
    for directory in dirs:
        for path in sorted(directory.glob("*.json")):
            for entry in _read(path):  # packaged data must be valid: let it raise
                entries[entry["id"]] = entry
        catalog.sources.append(str(directory))
    validate_catalog(list(entries.values()))

    if use_overlay and overlay_dir().is_dir():
        for path in sorted(overlay_dir().glob("*.json")):
            try:
                candidate = dict(entries)
                for entry in _read(path):
                    candidate[entry["id"]] = entry
                validate_catalog(list(candidate.values()))
            except (OSError, ValueError, SchemaError) as exc:
                catalog.problems.append(f"overlay {path.name} ignored: {exc}")
                continue
            entries = candidate
            catalog.sources.append(str(path))
    catalog.entries = entries
    return catalog
