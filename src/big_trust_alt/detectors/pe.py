"""Windows PE (.exe/.dll) reader: version info, architecture, .NET, signature.

Every offset read from the file is bounds-checked; malformed files raise
ValueError, never index errors or huge allocations.
"""

from __future__ import annotations

import os
import re
import struct

MAX_HEADER_OFFSET = 1 << 24
MAX_RESOURCE_BYTES = 1 << 20
MAX_SCAN = 8 << 20

MACHINES = {
    0x14C: "x86", 0x8664: "x86_64", 0x1C0: "arm", 0x1C4: "arm",
    0xAA64: "aarch64", 0x200: "ia64", 0x5064: "riscv64",
}
SUBSYSTEMS = {1: "native", 2: "gui", 3: "console", 9: "wince", 10: "efi", 16: "boot"}
VERSION_KEYS = (
    "ProductName", "CompanyName", "FileDescription", "ProductVersion",
    "FileVersion", "OriginalFilename", "InternalName", "LegalCopyright",
)
# Markers of common installer builders, searched in the first MAX_SCAN bytes.
INSTALLERS = (
    (b"Inno Setup Setup Data", "inno"),
    (b"Nullsoft Install System", "nsis"),
    (b"NullsoftInst", "nsis"),
    (b"InstallShield", "installshield"),
    (b"WixBundleManifest", "wix-burn"),
    (b".wixburn", "wix-burn"),
    (b"Squirrel", "squirrel"),
    (b"7zS.sfx", "7zip-sfx"),
    (b";!@Install@!UTF-8!", "7zip-sfx"),
    (b"Smart Install Maker", "smart-install-maker"),
    (b"InstallAware", "installaware"),
    (b"Setup Factory", "setup-factory"),
)
_REQUESTED_LEVEL = re.compile(rb'requestedExecutionLevel\s+level\s*=\s*"(\w+)"')


class Reader:
    def __init__(self, fd: int, size: int) -> None:
        self.fd = fd
        self.size = size

    def read(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset + length > self.size:
            raise ValueError("read out of bounds")
        data = os.pread(self.fd, length, offset)
        if len(data) != length:
            raise ValueError("short read")
        return data

    def unpack(self, fmt: str, offset: int):
        return struct.unpack(fmt, self.read(offset, struct.calcsize(fmt)))


def is_pe(head: bytes) -> bool:
    return head[:2] == b"MZ"


def parse(fd: int, size: int) -> dict[str, str]:
    r = Reader(fd, size)
    (lfanew,) = r.unpack("<I", 0x3C)
    if lfanew > min(size - 24, MAX_HEADER_OFFSET):
        raise ValueError("bad e_lfanew")
    if r.read(lfanew, 4) != b"PE\0\0":
        # Plain DOS program, no PE header.
        return {"pe.type": "dos"}
    machine, nsections, _, _, _, opt_size, characteristics = r.unpack("<HHIIIHH", lfanew + 4)
    opt = lfanew + 24
    (magic,) = r.unpack("<H", opt)
    if magic == 0x10B:
        dd_offset, count_offset = 96, 92
    elif magic == 0x20B:
        dd_offset, count_offset = 112, 108
    else:
        raise ValueError("bad optional header")
    (subsystem,) = r.unpack("<H", opt + 68)
    (ndirs,) = r.unpack("<I", opt + count_offset)
    ndirs = min(ndirs, 16)
    dirs = [r.unpack("<II", opt + dd_offset + 8 * i) for i in range(ndirs)]

    sections = []
    sec_table = opt + opt_size
    for i in range(min(nsections, 96)):
        name, vsize, vaddr, rawsize, rawptr = r.unpack("<8sIIII", sec_table + 40 * i)
        sections.append((name.rstrip(b"\0").decode("latin-1"), vaddr, max(vsize, rawsize), rawptr, rawsize))

    def rva_to_offset(rva: int) -> int:
        for _, vaddr, vsize, rawptr, rawsize in sections:
            if vaddr <= rva < vaddr + vsize:
                delta = rva - vaddr
                if delta >= rawsize:
                    raise ValueError("rva in virtual-only data")
                return rawptr + delta
        raise ValueError("rva outside sections")

    info: dict[str, str] = {
        "pe.type": "dll" if characteristics & 0x2000 else "exe",
        "pe.machine": MACHINES.get(machine, f"0x{machine:x}"),
        "pe.subsystem": SUBSYSTEMS.get(subsystem, str(subsystem)),
    }
    if ndirs > 14 and dirs[14][0] and dirs[14][1]:
        info["pe.dotnet"] = "yes"
    if ndirs > 4 and dirs[4][0] and dirs[4][1]:
        # The certificate table holds a file offset, not an RVA.
        cert_offset, cert_size = dirs[4]
        if cert_offset + cert_size <= size and cert_size >= 8:
            info["pe.signature"] = "present"

    end_of_sections = max((rawptr + rawsize for *_, rawptr, rawsize in sections), default=0)
    if end_of_sections and size > end_of_sections + 1024:
        info["pe.overlay"] = str(size - end_of_sections)

    if ndirs > 2 and dirs[2][0]:
        try:
            root = rva_to_offset(dirs[2][0])
            _read_resources(r, root, rva_to_offset, info)
        except (ValueError, struct.error):
            info["pe.resources"] = "damaged"

    head = os.pread(fd, min(size, MAX_SCAN), 0)
    for marker, kind in INSTALLERS:
        if marker in head:
            info["pe.installer"] = kind
            break
    return info


def _read_resources(r: Reader, root: int, rva_to_offset, info: dict[str, str]) -> None:
    def entries(directory: int):
        _, _, _, _, named, ids = r.unpack("<IIHHHH", directory)
        total = min(named + ids, 512)
        for i in range(total):
            name, target = r.unpack("<II", directory + 16 + 8 * i)
            yield name, target

    def first_leaf(target: int, depth: int = 0):
        # Follow subdirectories until a data entry (first name, first language).
        while target & 0x80000000:
            if depth > 3:
                raise ValueError("resource tree too deep")
            sub = root + (target & 0x7FFFFFFF)
            target = next((t for _, t in entries(sub)), None)
            if target is None:
                return None
            depth += 1
        rva, length, _, _ = r.unpack("<IIII", root + target)
        if not 0 < length <= MAX_RESOURCE_BYTES:
            raise ValueError("bad resource size")
        return r.read(rva_to_offset(rva), length)

    for name, target in entries(root):
        if name == 16:      # RT_VERSION
            data = first_leaf(target)
            if data:
                info.update(parse_version_info(data))
        elif name == 24:    # RT_MANIFEST
            data = first_leaf(target)
            if data:
                m = _REQUESTED_LEVEL.search(data)
                if m:
                    info["pe.requested_level"] = m.group(1).decode("ascii", "replace")


def parse_version_info(data: bytes) -> dict[str, str]:
    """Parse a VS_VERSIONINFO block into the string fields we care about."""
    found: dict[str, str] = {}

    def block(offset: int, end: int, depth: int) -> int:
        if offset + 6 > end or depth > 4:
            return end
        length, value_len, value_type = struct.unpack_from("<HHH", data, offset)
        if length < 6:
            return end
        stop = min(offset + length, end)
        key_start = offset + 6
        key_end = key_start
        while key_end + 1 < stop and data[key_end:key_end + 2] != b"\0\0":
            key_end += 2
        key = data[key_start:key_end].decode("utf-16-le", "replace")
        pos = _align(key_end + 2)
        if value_len:
            # value_len counts WORDs for text values and bytes for binary ones.
            byte_len = value_len * 2 if value_type == 1 else value_len
            if depth >= 3 and value_type == 1 and key in VERSION_KEYS and key not in found:
                text = data[pos:min(pos + byte_len, stop)].decode("utf-16-le", "replace")
                text = text.split("\0", 1)[0].strip()
                if text:
                    found[key] = text[:200]
            pos = _align(pos + byte_len)
        while pos < stop:
            nxt = block(pos, stop, depth + 1)
            if nxt <= pos:
                break
            pos = _align(nxt)
        return stop

    try:
        block(0, len(data), 0)
    except struct.error:
        pass
    return {f"pe.{k}": v for k, v in found.items()}


def _align(n: int) -> int:
    return (n + 3) & ~3
