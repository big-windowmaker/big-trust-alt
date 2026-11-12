import copy
import json
from pathlib import Path

import pytest

from big_trust_alt.database import catalog as catalog_mod
from big_trust_alt.database.normalize import normalize_filename
from big_trust_alt.database.schema import SchemaError, validate_catalog, validate_entry

ROOT = Path(__file__).resolve().parent.parent
GOOD = {"id": "x", "name": "X", "category": "utilities", "kind": "application", "match": {"filenames": ["xsetup*"]},
        "linux": {"packages": ["x"]}, "verified": "2026-11-12", "provenance": ["pacman"]}


@pytest.mark.parametrize("change,message", [
    (lambda e: e["match"].update(filenames=["*"]), "invalid value"),
    (lambda e: e["match"].update(filenames=["ab*"]), "too generic"),
    (lambda e: e["match"].update(filenames=["(a+)+$"]), "invalid value"),
    (lambda e: e["linux"].update(flatpak=["not an id"]), "invalid value"),
    (lambda e: e["linux"].update(website="http://insecure.example"), "https"),
    (lambda e: e.update(verified="2019-01-01"), "too old"),
    (lambda e: e.update(category="nope"), "unknown category"),
    (lambda e: e.update(extra=1), "unknown keys"),
    (lambda e: e.pop("linux"), "offers nothing"),
])
def test_schema_rejects(change, message):
    entry = copy.deepcopy(GOOD)
    change(entry)
    with pytest.raises(SchemaError, match=message):
        validate_entry(entry)


def test_alternatives_must_exist():
    entry = copy.deepcopy(GOOD)
    entry["alternatives"] = [{"id": "missing", "relation": "alternative"}]
    with pytest.raises(SchemaError, match="not in the catalog"):
        validate_catalog([entry])


def test_normalize():
    assert normalize_filename("Firefox Setup 133.0.exe") == "firefox setup 133 0"
    assert normalize_filename("npp.8.6.Installer.x64.exe") == "npp 8 6 installer x64"
    assert normalize_filename("Notepad++.exe") == "notepad++"
    assert normalize_filename("ÁUDIO.msi") == "audio"


def test_overlay_invalid_is_ignored(tmp_path, monkeypatch):
    overlay = catalog_mod.overlay_dir()
    overlay.mkdir(parents=True)
    (overlay / "bad.json").write_text('{"schema_version": 1, "entries": [{"id": "BAD"}]}')
    good = {"schema_version": 1, "entries": [GOOD]}
    (overlay / "good.json").write_text(json.dumps(good))
    cat = catalog_mod.load(extra_dirs=[ROOT / "tests/fixtures/catalog"])
    assert "x" in cat.entries
    assert any("bad.json" in p for p in cat.problems)


def test_shipped_catalog_is_valid():
    files = sorted((ROOT / "data/app-db/catalog").glob("*.json"))
    if not files:
        pytest.skip("catalog not generated yet")
    cat = catalog_mod.load(use_overlay=False)
    assert len(cat) > 100


def test_catalog_globs_do_not_collide():
    """Every sample installer name matches only its own entry; tricky names match what is expected."""
    import fnmatch
    data = json.loads((ROOT / "tests/fixtures/catalog_samples.json").read_text(encoding="utf-8"))
    cat = catalog_mod.load(use_overlay=False)
    globs = [(g, e["id"]) for e in cat.entries.values() for g in e["match"].get("filenames", ())]

    def hits(name):
        n = normalize_filename(name)
        return sorted({eid for g, eid in globs if fnmatch.fnmatchcase(n, g)})

    failures = []
    for eid, names in data["samples"].items():
        if eid not in cat.entries:
            continue
        failures += [(name, hits(name), [eid]) for name in names if hits(name) != [eid]]
    failures += [(name, hits(name), sorted(exp)) for name, exp in data["negatives"].items() if hits(name) != sorted(exp)]
    assert not failures, failures[:10]
