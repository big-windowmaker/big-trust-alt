"""Catalog schema (version 1) and its validator.

The validator is the authority: the JSON Schema in data/schemas is
documentation for contributors and editors. No third-party dependency.
"""

from __future__ import annotations

import re
from datetime import date

SCHEMA_VERSION = 1

CATEGORIES = frozenset({
    "browser", "communication", "email", "office", "documents", "notes",
    "graphics", "photo", "video", "audio", "music", "media-server",
    "games", "game-launcher", "emulator", "development", "database",
    "network", "remote-desktop", "file-transfer", "cloud-storage",
    "archive", "security", "password-manager", "vpn", "system",
    "utilities", "education", "science", "ai", "virtualization",
    "runtime", "hardware", "finance", "design", "3d",
})
KINDS = frozenset({"application", "runtime", "game", "launcher", "security", "system"})
PLATFORMS = frozenset({"windows", "linux", "web", "macos"})
FORMATS = frozenset({
    "exe", "msi", "msix", "appx", "bat", "cmd", "ps1", "deb", "rpm",
    "appimage", "run", "bin", "sh", "jar", "flatpakref", "flatpak",
    "arch-package", "tarball", "dmg",
})
RELATIONS = frozenset({"successor", "alternative", "web", "launcher"})
WINE = frozenset({"works", "partial", "unsupported", "unknown", "not-needed"})
PROVENANCE = frozenset({
    "zorin-exec-guard-app-db", "big-trust-alt", "pacman", "aur", "flathub",
    "appstream", "vendor", "user-attachment",
})

ID_RE = re.compile(r"[a-z0-9][a-z0-9.+-]{0,63}")
PKG_RE = re.compile(r"[a-z0-9@_+][a-z0-9@._+-]{0,127}")
FLATPAK_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*(\.[A-Za-z0-9_-]+){2,}")
DESKTOP_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.desktop")
# Globs are matched against the normalized file name (see matcher.normalize):
# lowercase letters, digits, single spaces and the wildcards * and ?.
GLOB_RE = re.compile(r"[a-z0-9 *?+]{2,64}")
TEXT_RE = re.compile(r"[^\x00-\x1f\x7f]{1,160}")
LANGS = frozenset({"en", "pt_BR"})

ENTRY_KEYS = {
    "id", "name", "aliases", "vendor", "category", "kind", "platforms",
    "match", "linux", "alternatives", "windows", "message", "verified",
    "provenance",
}
MATCH_KEYS = {"filenames", "products", "vendors", "packages", "formats"}
LINUX_KEYS = {"packages", "flatpak", "desktop", "website", "instructions", "steam"}
ALT_KEYS = {"id", "relation", "note"}
WINDOWS_KEYS = {"wine", "note"}


class SchemaError(ValueError):
    """A catalog document does not follow the schema."""


def _err(path: str, msg: str) -> SchemaError:
    return SchemaError(f"{path}: {msg}")


def _keys(obj, allowed: set[str], path: str, required: tuple[str, ...] = ()) -> None:
    if not isinstance(obj, dict):
        raise _err(path, "must be an object")
    extra = set(obj) - allowed
    if extra:
        raise _err(path, f"unknown keys {sorted(extra)}")
    for key in required:
        if key not in obj:
            raise _err(path, f"missing '{key}'")


def _text(value, path: str) -> None:
    if not isinstance(value, str) or not TEXT_RE.fullmatch(value) or value != value.strip():
        raise _err(path, "must be a non-empty single-line string up to 160 chars")


def _list(value, path: str, regex: re.Pattern | None = None, enum=None, max_len: int = 32) -> None:
    if not isinstance(value, list) or not value or len(value) > max_len:
        raise _err(path, f"must be a non-empty list with up to {max_len} items")
    if len(set(map(str, value))) != len(value):
        raise _err(path, "has duplicate items")
    for i, item in enumerate(value):
        if enum is not None:
            if item not in enum:
                raise _err(f"{path}[{i}]", f"'{item}' is not one of {sorted(enum)}")
        elif regex is not None:
            if not isinstance(item, str) or not regex.fullmatch(item):
                raise _err(f"{path}[{i}]", f"invalid value {item!r}")
        else:
            _text(item, f"{path}[{i}]")


def _https(value, path: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"https://[^\s\"<>]{3,300}", value):
        raise _err(path, "must be an https:// URL")


def _i18n(value, path: str) -> None:
    _keys(value, set(LANGS), path, required=("en",))
    for lang, text in value.items():
        if not isinstance(text, str) or not 1 <= len(text) <= 400 or "\x00" in text:
            raise _err(f"{path}.{lang}", "must be a string up to 400 chars")


def validate_entry(entry, path: str = "entry") -> None:
    _keys(entry, ENTRY_KEYS, path,
          required=("id", "name", "category", "kind", "match", "verified", "provenance"))
    if not isinstance(entry["id"], str) or not ID_RE.fullmatch(entry["id"]):
        raise _err(f"{path}.id", "must match [a-z0-9][a-z0-9.+-]*")
    _text(entry["name"], f"{path}.name")
    if "aliases" in entry:
        _list(entry["aliases"], f"{path}.aliases")
    if "vendor" in entry:
        _text(entry["vendor"], f"{path}.vendor")
    if entry["category"] not in CATEGORIES:
        raise _err(f"{path}.category", f"unknown category {entry['category']!r}")
    if entry["kind"] not in KINDS:
        raise _err(f"{path}.kind", f"unknown kind {entry['kind']!r}")
    if "platforms" in entry:
        _list(entry["platforms"], f"{path}.platforms", enum=PLATFORMS)

    match = entry["match"]
    _keys(match, MATCH_KEYS, f"{path}.match")
    if not ({"filenames", "products", "packages"} & set(match)):
        raise _err(f"{path}.match", "needs filenames, products or packages")
    if "filenames" in match:
        _list(match["filenames"], f"{path}.match.filenames", GLOB_RE)
        for i, glob in enumerate(match["filenames"]):
            if len(glob.replace("*", "").replace("?", "").replace(" ", "")) < 3:
                raise _err(f"{path}.match.filenames[{i}]", "too generic (fewer than 3 literal chars)")
            if glob.count("*") > 4:
                raise _err(f"{path}.match.filenames[{i}]", "more than 4 wildcards")
    for key in ("products", "vendors"):
        if key in match:
            _list(match[key], f"{path}.match.{key}")
            for i, item in enumerate(match[key]):
                if item != item.lower():
                    raise _err(f"{path}.match.{key}[{i}]", "must be lowercase (normalized)")
    if "packages" in match:
        _list(match["packages"], f"{path}.match.packages", PKG_RE)
    if "formats" in match:
        _list(match["formats"], f"{path}.match.formats", enum=FORMATS)

    if "linux" in entry:
        linux = entry["linux"]
        _keys(linux, LINUX_KEYS, f"{path}.linux")
        if not linux:
            raise _err(f"{path}.linux", "must not be empty")
        if "packages" in linux:
            _list(linux["packages"], f"{path}.linux.packages", PKG_RE, max_len=8)
        if "flatpak" in linux:
            _list(linux["flatpak"], f"{path}.linux.flatpak", FLATPAK_RE, max_len=4)
        if "desktop" in linux:
            _list(linux["desktop"], f"{path}.linux.desktop", DESKTOP_RE, max_len=8)
        for key in ("website", "instructions"):
            if key in linux:
                _https(linux[key], f"{path}.linux.{key}")
        if "steam" in linux and (not isinstance(linux["steam"], str) or not linux["steam"].isdigit()):
            raise _err(f"{path}.linux.steam", "must be a numeric Steam app id")

    if "alternatives" in entry:
        alts = entry["alternatives"]
        if not isinstance(alts, list) or not alts or len(alts) > 8:
            raise _err(f"{path}.alternatives", "must be a non-empty list up to 8 items")
        seen = set()
        for i, alt in enumerate(alts):
            apath = f"{path}.alternatives[{i}]"
            _keys(alt, ALT_KEYS, apath, required=("id", "relation"))
            if not isinstance(alt["id"], str) or not ID_RE.fullmatch(alt["id"]):
                raise _err(f"{apath}.id", "invalid id")
            if alt["id"] in seen or alt["id"] == entry["id"]:
                raise _err(f"{apath}.id", "duplicate or self reference")
            seen.add(alt["id"])
            if alt["relation"] not in RELATIONS:
                raise _err(f"{apath}.relation", f"must be one of {sorted(RELATIONS)}")
            if "note" in alt:
                _i18n(alt["note"], f"{apath}.note")

    if "windows" in entry:
        win = entry["windows"]
        _keys(win, WINDOWS_KEYS, f"{path}.windows", required=("wine",))
        if win["wine"] not in WINE:
            raise _err(f"{path}.windows.wine", f"must be one of {sorted(WINE)}")
        if "note" in win:
            _i18n(win["note"], f"{path}.windows.note")
    if "message" in entry:
        _i18n(entry["message"], f"{path}.message")

    try:
        when = date.fromisoformat(entry["verified"])
    except (TypeError, ValueError):
        raise _err(f"{path}.verified", "must be an ISO date YYYY-MM-DD") from None
    if when.year < 2024:
        raise _err(f"{path}.verified", "too old to be trusted")
    _list(entry["provenance"], f"{path}.provenance", enum=PROVENANCE)

    has_linux = "linux" in entry
    if not has_linux and "alternatives" not in entry and "message" not in entry:
        raise _err(path, "offers nothing: add linux, alternatives or message")


def validate_document(doc, path: str = "document") -> list[dict]:
    """Validate one catalog file and return its entries."""
    _keys(doc, {"schema_version", "entries"}, path, required=("schema_version", "entries"))
    if doc["schema_version"] != SCHEMA_VERSION:
        raise _err(f"{path}.schema_version", f"unsupported version {doc['schema_version']!r}")
    entries = doc["entries"]
    if not isinstance(entries, list) or not entries:
        raise _err(f"{path}.entries", "must be a non-empty list")
    for i, entry in enumerate(entries):
        validate_entry(entry, f"{path}.entries[{i}]")
    return entries


def validate_catalog(entries: list[dict]) -> None:
    """Cross-entry checks: unique ids and alternatives that resolve."""
    ids: dict[str, int] = {}
    for i, entry in enumerate(entries):
        if entry["id"] in ids:
            raise SchemaError(f"duplicate id {entry['id']!r}")
        ids[entry["id"]] = i
    for entry in entries:
        for alt in entry.get("alternatives", ()):
            if alt["id"] not in ids:
                raise SchemaError(f"{entry['id']}: alternative {alt['id']!r} is not in the catalog")
            target = entries[ids[alt["id"]]]
            if alt["relation"] != "web" and "linux" not in target:
                raise SchemaError(f"{entry['id']}: alternative {alt['id']!r} has no linux block")
