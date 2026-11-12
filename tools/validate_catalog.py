#!/usr/bin/env python3
"""Validate every catalog file: schema, unique ids, alternatives."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from big_trust_alt.database.schema import SchemaError, validate_catalog, validate_document  # noqa: E402


def main() -> int:
    entries = []
    files = sorted((ROOT / "data/app-db/catalog").glob("*.json"))
    try:
        for path in files:
            with path.open(encoding="utf-8") as fh:
                entries += validate_document(json.load(fh), path.name)
        validate_catalog(entries)
    except (SchemaError, json.JSONDecodeError) as exc:
        print(f"catalog: {exc}", file=sys.stderr)
        return 1
    print(f"catalog: {len(files)} files, {len(entries)} entries, ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
