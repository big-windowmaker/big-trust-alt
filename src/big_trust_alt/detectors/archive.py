"""Zip based (.jar, .msix, .appx) and tar based (.pkg.tar.*, tarballs) readers.

Only metadata members are read, with size limits; nothing is extracted to disk.
"""

from __future__ import annotations

import os
import tarfile
import xml.etree.ElementTree as ET
import zipfile

from .compress import MAX_OUTPUT

MAX_MEMBER = 1 << 20
MAX_LIST = 2000


class _FdFile:
    """Read-only file object over a file descriptor (no seek past EOF writes)."""

    def __init__(self, fd: int, size: int) -> None:
        self.fd, self.size, self.pos = fd, size, 0

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            n = self.size - self.pos
        data = os.pread(self.fd, max(0, min(n, self.size - self.pos)), self.pos)
        self.pos += len(data)
        return data

    def seek(self, offset: int, whence: int = 0) -> int:
        base = {0: 0, 1: self.pos, 2: self.size}[whence]
        self.pos = max(0, base + offset)
        return self.pos

    def tell(self) -> int:
        return self.pos

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True


def is_zip(head: bytes) -> bool:
    return head[:4] == b"PK\x03\x04"


def parse_zip(fd: int, size: int) -> tuple[str, dict[str, str]]:
    """Return (format, metadata) for jar/msix/appx/zip."""
    with zipfile.ZipFile(_FdFile(fd, size)) as zf:
        names = zf.namelist()[:MAX_LIST]
        lower = {n.lower(): n for n in names}
        if "appxmanifest.xml" in lower:
            return "msix", _appx(zf, lower["appxmanifest.xml"])
        if "appxmetadata/appxbundlemanifest.xml" in lower:
            return "msix", _appx(zf, lower["appxmetadata/appxbundlemanifest.xml"], bundle=True)
        if "meta-inf/manifest.mf" in lower:
            return "jar", _jar(zf, lower["meta-inf/manifest.mf"], names)
        exes = [n for n in names if n.lower().endswith((".exe", ".msi"))]
        info = {"zip.entries": str(len(names))}
        if exes:
            info["zip.windows_programs"] = ", ".join(os.path.basename(n) for n in exes[:5])
        return "zip", info


def _member(zf: zipfile.ZipFile, name: str) -> bytes:
    if zf.getinfo(name).file_size > MAX_MEMBER:
        raise ValueError("member too large")
    return zf.read(name)


def _jar(zf, name, names) -> dict[str, str]:
    info = {}
    text = _member(zf, name).decode("utf-8", "replace")
    for line in text.splitlines():
        key, _, value = line.partition(":")
        if key in ("Main-Class", "Implementation-Title", "Implementation-Vendor",
                   "Implementation-Version", "Bundle-Name", "Application-Name",
                   "Created-By", "Launcher-Agent-Class") and value.strip():
            info[f"jar.{key}"] = value.strip()[:200]
    info["jar.runnable"] = "yes" if "jar.Main-Class" in info else "no"
    if any(n.endswith(".dll") for n in names):
        info["jar.native_windows"] = "yes"
    return info


def _appx(zf, name, bundle: bool = False) -> dict[str, str]:
    raw = _member(zf, name)
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise ValueError("manifest with DTD refused")
    root = ET.fromstring(raw)  # noqa: S314 - DTDs and entities are refused above; size is capped
    info = {"msix.bundle": "yes" if bundle else "no"}
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "Identity" and "msix.Name" not in info:
            info["msix.Name"] = el.get("Name", "")[:200]
            info["msix.Publisher"] = el.get("Publisher", "")[:300]
            info["msix.Version"] = el.get("Version", "")[:50]
            if el.get("ProcessorArchitecture"):
                info["msix.Architecture"] = el.get("ProcessorArchitecture")[:20]
        elif tag in ("DisplayName", "PublisherDisplayName") and el.text and f"msix.{tag}" not in info:
            info[f"msix.{tag}"] = el.text.strip()[:200]
    return {k: v for k, v in info.items() if v}


TAR_MAGICS = (b"\x1f\x8b", b"\xfd7zXZ\x00", b"\x28\xb5\x2f\xfd", b"BZh")


def is_tar(head: bytes) -> bool:
    return head.startswith(TAR_MAGICS) or head[257:262] == b"ustar"


def parse_tar(fd: int, size: int, name: str) -> tuple[str, dict[str, str]]:
    """Look at the first members of a (compressed) tar: Arch package or tarball."""
    import gzip
    import lzma
    import bz2

    head = os.pread(fd, 8, 0)
    raw = _FdFile(fd, size)
    if head.startswith(b"\x1f\x8b"):
        stream = gzip.GzipFile(fileobj=raw)
    elif head.startswith(b"\xfd7zXZ"):
        stream = lzma.LZMAFile(raw)
    elif head.startswith(b"\x28\xb5\x2f\xfd"):
        from compression import zstd
        stream = zstd.ZstdFile(raw)
    elif head.startswith(b"BZh"):
        stream = bz2.BZ2File(raw)
    else:
        stream = raw
    info: dict[str, str] = {}
    members: list[str] = []
    budget = MAX_OUTPUT
    with tarfile.open(fileobj=stream, mode="r|") as tar:
        for count, member in enumerate(tar):
            if count >= 400:
                info["tar.truncated"] = "yes"
                break
            budget -= member.size
            if budget < 0:
                info["tar.truncated"] = "yes"
                break
            members.append(member.name)
            if member.name == ".PKGINFO" and member.isfile() and member.size <= MAX_MEMBER:
                text = tar.extractfile(member).read().decode("utf-8", "replace")
                for line in text.splitlines():
                    key, _, value = line.partition(" = ")
                    if key in ("pkgname", "pkgver", "pkgdesc", "url", "arch", "packager") and value:
                        info.setdefault(f"pkg.{key}", value.strip()[:300])
    if "pkg.pkgname" in info:
        return "arch-package", info
    info["tar.members"] = str(len(members))
    hints = [m for m in members if m.rsplit("/", 1)[-1].lower() in (
        "install.sh", "install", "configure", "makefile", "cmakelists.txt", "setup.py",
        "meson.build", "pkgbuild", "readme", "readme.md", "install.md")]
    if hints:
        info["tar.hints"] = ", ".join(sorted({h.rsplit("/", 1)[-1] for h in hints})[:6])
    desktop = [m for m in members if m.endswith(".desktop")]
    if desktop:
        info["tar.desktop"] = desktop[0].rsplit("/", 1)[-1][:120]
    if any(m.lower().endswith(".exe") for m in members):
        info["tar.windows_programs"] = "yes"
    return "tarball", info
