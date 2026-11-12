"""Debian package (.deb) reader: the control file, without extracting data."""

from __future__ import annotations

import io
import os
import tarfile

from .compress import open_compressed

MAX_CONTROL = 8 << 20
FIELDS = ("Package", "Version", "Architecture", "Maintainer", "Description", "Homepage", "Section")


def is_deb(head: bytes) -> bool:
    return head.startswith(b"!<arch>\ndebian-binary")


def parse(fd: int, size: int) -> dict[str, str]:
    offset = 8
    for _ in range(16):
        hdr = os.pread(fd, 60, offset)
        if len(hdr) < 60 or hdr[58:60] != b"`\n":
            break
        name = hdr[:16].decode("ascii", "replace").strip().rstrip("/")
        length = int(hdr[48:58].strip() or 0)
        start = offset + 60
        if name.startswith("control.tar"):
            if length > MAX_CONTROL or start + length > size:
                raise ValueError("control archive too large")
            raw = os.pread(fd, length, start)
            return _control(open_compressed(name, raw))
        offset = start + length + (length & 1)
    raise ValueError("control archive not found")


def _control(raw: bytes) -> dict[str, str]:
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
        for count, member in enumerate(tar):
            if count > 64:
                break
            if member.isfile() and member.name.lstrip("./") == "control" and member.size <= 1 << 20:
                text = tar.extractfile(member).read().decode("utf-8", "replace")
                return parse_fields(text, "deb")
    raise ValueError("control file not found")


def parse_fields(text: str, prefix: str) -> dict[str, str]:
    info = {}
    for line in text.splitlines():
        if not line or line[0] in " \t" or ":" not in line:
            continue
        key, _, value = line.partition(":")
        if key in FIELDS and value.strip():
            info[f"{prefix}.{key}"] = value.strip()[:300]
    return info
