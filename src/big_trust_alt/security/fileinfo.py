"""Open a file without following tricks, hash it, and read where it came from.

Nothing here executes, extracts or modifies the file.
"""

from __future__ import annotations

import hashlib
import os
import stat
import unicodedata
from urllib.parse import urlsplit

from ..core.model import FileIdentity, FileReport, Severity

CHUNK = 1 << 20
# Bidirectional and invisible characters used to disguise extensions,
# e.g. "invoice‮fdp.exe" is displayed as "invoiceexe.pdf".
_DECEPTIVE = {
    "‪", "‫", "‬", "‭", "‮",
    "⁦", "⁧", "⁨", "⁩", "‎", "‏",
    "​", "‌", "‍", "⁠", "﻿",
}
_DOCUMENT_EXTS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "txt",
    "jpg", "jpeg", "png", "gif", "mp3", "mp4", "avi", "mkv", "zip", "rar",
}
_RUNNABLE_EXTS = {"exe", "msi", "scr", "bat", "cmd", "com", "pif", "js", "vbs",
                  "ps1", "sh", "run", "bin", "appimage", "jar", "desktop"}


class FileAccessError(Exception):
    """The file cannot be analyzed; the message is safe to show."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def open_regular(path: str) -> tuple[int, os.stat_result, str]:
    """Open `path` read-only and make sure it is a regular file.

    Symlinks are resolved once (the report records the target) and the
    final component is opened with O_NOFOLLOW, so a link swapped in after
    resolution is refused instead of followed.
    """
    try:
        resolved = os.path.realpath(path, strict=True)
    except FileNotFoundError:
        raise FileAccessError("not-found") from None
    except (OSError, RuntimeError) as exc:
        raise FileAccessError("unreadable", str(exc)) from None
    target = resolved if os.path.islink(path) else ""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | getattr(os, "O_NOCTTY", 0) | os.O_NONBLOCK
    try:
        fd = os.open(resolved, flags)
    except PermissionError:
        raise FileAccessError("permission-denied") from None
    except FileNotFoundError:
        raise FileAccessError("not-found") from None
    except OSError as exc:
        raise FileAccessError("unreadable", exc.strerror or str(exc)) from None
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        os.close(fd)
        raise FileAccessError("not-regular")
    return fd, st, target


def sha256_fd(fd: int, cancel=None) -> str:
    digest = hashlib.sha256()
    offset = 0
    while True:
        if cancel is not None and cancel():
            raise FileAccessError("cancelled")
        chunk = os.pread(fd, CHUNK, offset)
        if not chunk:
            return digest.hexdigest()
        digest.update(chunk)
        offset += len(chunk)


def identity_of(fd: int, st: os.stat_result, cancel=None) -> FileIdentity:
    return FileIdentity(st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, sha256_fd(fd, cancel))


def verify_unchanged(path: str, expected: FileIdentity) -> bool:
    """True when `path` is still exactly the file that was analyzed."""
    try:
        fd, st, _ = open_regular(path)
    except FileAccessError:
        return False
    try:
        if (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns) != (
            expected.device, expected.inode, expected.size, expected.mtime_ns
        ):
            return False
        return sha256_fd(fd) == expected.sha256
    finally:
        os.close(fd)


def read_origin(path: str) -> tuple[str, str]:
    """Download origin recorded by browsers (Firefox, Chromium) in xattrs."""
    values = []
    for attr in ("user.xdg.origin.url", "user.xdg.referrer.url"):
        try:
            raw = os.getxattr(path, attr)
        except OSError:
            values.append("")
            continue
        values.append(_clean_url(raw.decode("utf-8", "replace")))
    return values[0], values[1]


def _clean_url(url: str) -> str:
    url = url.strip()[:2048]
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https", "ftp") or not parts.hostname:
        return ""
    # Drop credentials and query strings (they can carry tokens).
    host = parts.hostname + (f":{parts.port}" if parts.port else "")
    return f"{parts.scheme}://{host}{parts.path}"


def host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def check_name(report: FileReport) -> None:
    """Findings about the file name itself."""
    name = report.name
    if any(ch in _DECEPTIVE for ch in name):
        report.add("deceptive-name", Severity.DANGER,
                   "".join(f"U+{ord(c):04X} " for c in name if c in _DECEPTIVE).strip())
    if any(unicodedata.category(ch) == "Cc" for ch in name):
        report.add("control-chars-in-name", Severity.WARNING)
    parts = name.lower().split(".")
    if len(parts) >= 3 and parts[-1] in _RUNNABLE_EXTS and parts[-2] in _DOCUMENT_EXTS:
        report.add("double-extension", Severity.DANGER, f".{parts[-2]}.{parts[-1]}")
    if len(name) > 200:
        report.add("long-name", Severity.WARNING)


def display_name(name: str) -> str:
    """A version of the name that is safe to show: deceptive characters made visible."""
    out = []
    for ch in name:
        if ch in _DECEPTIVE or unicodedata.category(ch) in ("Cc", "Cf"):
            out.append(f"<U+{ord(ch):04X}>")
        else:
            out.append(ch)
    return "".join(out)
