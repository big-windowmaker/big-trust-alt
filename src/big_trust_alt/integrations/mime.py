"""File associations through mimeapps.list (XDG), reversible.

Installing the package writes no default: the .desktop file only declares
the Windows types, so Big Trust Alt becomes a candidate for them.
`associate()` makes it the explicit default for the Windows types (saving the
previous defaults) and adds it to "Open with" for the Linux formats without
changing their defaults; `dissociate()` undoes both.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from ..core.settings import load_settings, save_settings

DESKTOP_ID = "io.github.big_windowmaker.BigTrustAlt.desktop"
WINDOWS_TYPES = (
    "application/x-ms-dos-executable",
    "application/x-msdownload",
    "application/vnd.microsoft.portable-executable",
    "application/x-msi",
    "application/msix",
    "application/appx",
    "application/x-bat",
)
LINUX_TYPES = (
    "application/vnd.debian.binary-package",
    "application/x-rpm",
    "application/vnd.appimage",
    "application/java-archive",
    "application/vnd.flatpak.ref",
    "application/x-shellscript",
    "text/x-shellscript",
)
ADDED = "Added Associations"
SECTION = "Default Applications"


def mimeapps_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "mimeapps.list"


def _read() -> configparser.ConfigParser:
    cp = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
    cp.optionxform = str
    try:
        cp.read(mimeapps_path(), encoding="utf-8")
    except configparser.Error:
        pass
    return cp


def _write(cp: configparser.ConfigParser) -> None:
    path = mimeapps_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.big-trust-alt.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        cp.write(fh, space_around_delimiters=False)
    os.replace(tmp, path)


def status() -> list[tuple[str, str, bool]]:
    cp = _read()
    out = []
    for mime_type in WINDOWS_TYPES:
        current = cp.get(SECTION, mime_type, fallback="").split(";")[0]
        out.append((mime_type, current, current == DESKTOP_ID))
    return out


def associate() -> list[str]:
    cp = _read()
    if not cp.has_section(SECTION):
        cp.add_section(SECTION)
    settings = load_settings()
    backup = settings.get("mime_backup") or {}
    changed = []
    for mime_type in WINDOWS_TYPES:
        current = cp.get(SECTION, mime_type, fallback="")
        if current.split(";")[0] == DESKTOP_ID:
            continue
        backup.setdefault(mime_type, current)
        cp.set(SECTION, mime_type, f"{DESKTOP_ID};")
        changed.append(mime_type)
    if not cp.has_section(ADDED):
        cp.add_section(ADDED)
    for mime_type in LINUX_TYPES:
        current = [x for x in cp.get(ADDED, mime_type, fallback="").split(";") if x]
        if DESKTOP_ID not in current:
            cp.set(ADDED, mime_type, ";".join([*current, DESKTOP_ID]) + ";")
            changed.append(mime_type)
    if changed:
        settings["mime_backup"] = backup
        save_settings(settings)
        _write(cp)
    return changed


def dissociate() -> list[str]:
    cp = _read()
    settings = load_settings()
    backup = settings.get("mime_backup") or {}
    restored = []
    for mime_type in WINDOWS_TYPES:
        current = cp.get(SECTION, mime_type, fallback="")
        if current.split(";")[0] != DESKTOP_ID:
            continue
        previous = backup.get(mime_type, "")
        if previous:
            cp.set(SECTION, mime_type, previous)
        else:
            cp.remove_option(SECTION, mime_type)
        restored.append(mime_type)
    for mime_type in LINUX_TYPES:
        current = [x for x in cp.get(ADDED, mime_type, fallback="").split(";") if x]
        if DESKTOP_ID in current:
            rest = [x for x in current if x != DESKTOP_ID]
            if rest:
                cp.set(ADDED, mime_type, ";".join(rest) + ";")
            else:
                cp.remove_option(ADDED, mime_type)
            restored.append(mime_type)
    settings["mime_backup"] = {}
    save_settings(settings)
    if restored:
        _write(cp)
    return restored
