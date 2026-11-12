"""Text normalization shared by the catalog and the matcher."""

from __future__ import annotations

import re
import unicodedata

# Extensions removed before matching file names; longest first.
KNOWN_SUFFIXES = (
    ".pkg.tar.zst", ".pkg.tar.xz", ".tar.gz", ".tar.xz", ".tar.zst", ".tar.bz2",
    ".appimage", ".flatpakref", ".flatpak", ".msix", ".appx", ".exe", ".msi",
    ".deb", ".rpm", ".run", ".bin", ".jar", ".bat", ".cmd", ".ps1", ".sh",
    ".tgz", ".zip", ".dmg",
)
_NON_WORD = re.compile(r"[^a-z0-9+]+")


def fold(text: str) -> str:
    """Lowercase, strip accents and collapse everything else into spaces."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return _NON_WORD.sub(" ", text).strip()


def normalize_filename(name: str) -> str:
    """'Firefox Setup 133.0.exe' -> 'firefox setup 133 0'."""
    lower = name.lower()
    for suffix in KNOWN_SUFFIXES:
        if lower.endswith(suffix) and len(lower) > len(suffix):
            name = name[: -len(suffix)]
            break
    return fold(name)[:200]
