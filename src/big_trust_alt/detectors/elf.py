"""ELF reader: architecture, AppImage type and AppImage update information."""

from __future__ import annotations

import os
import struct

MACHINES = {3: "x86", 0x3E: "x86_64", 0x28: "arm", 0xB7: "aarch64", 0xF3: "riscv64",
            0x08: "mips", 0x14: "ppc", 0x15: "ppc64", 0x16: "s390x"}
TYPES = {1: "relocatable", 2: "executable", 3: "shared", 4: "core"}
APPIMAGE_SECTIONS = (".upd_info", ".sha256_sig", ".sig_key", ".digest_md5")


def is_elf(head: bytes) -> bool:
    return head[:4] == b"\x7fELF"


def parse(fd: int, size: int) -> dict[str, str]:
    ident = os.pread(fd, 64, 0)
    if len(ident) < 52:
        raise ValueError("truncated ELF header")
    cls, data = ident[4], ident[5]
    if cls not in (1, 2) or data not in (1, 2):
        raise ValueError("bad ELF class")
    end = "<" if data == 1 else ">"
    info = {"elf.class": "64" if cls == 2 else "32"}
    e_type, machine = struct.unpack_from(end + "HH", ident, 16)
    info["elf.machine"] = MACHINES.get(machine, f"0x{machine:x}")
    info["elf.type"] = TYPES.get(e_type, str(e_type))
    if ident[8:11] in (b"AI\x01", b"AI\x02"):
        info["appimage.type"] = str(ident[10])
    if cls == 2:
        shoff, = struct.unpack_from(end + "Q", ident, 0x28)
        shentsize, shnum, shstrndx = struct.unpack_from(end + "HHH", ident, 0x3A)
    else:
        shoff, = struct.unpack_from(end + "I", ident, 0x20)
        shentsize, shnum, shstrndx = struct.unpack_from(end + "HHH", ident, 0x2E)
    if "appimage.type" in info and 0 < shnum <= 512 and shentsize >= 40 and shoff + shnum * shentsize <= size:
        try:
            info.update(_appimage_sections(fd, size, end, cls, shoff, shentsize, shnum, shstrndx))
        except (ValueError, struct.error):
            info["appimage.sections"] = "damaged"
    return info


def _appimage_sections(fd, size, end, cls, shoff, shentsize, shnum, shstrndx) -> dict[str, str]:
    table = os.pread(fd, shnum * shentsize, shoff)
    fmt = end + ("IIQQQQ" if cls == 2 else "IIIIII")

    def section(i):
        name, _, _, _, offset, length = struct.unpack_from(fmt, table, i * shentsize)
        return name, offset, length

    if shstrndx >= shnum:
        raise ValueError("bad shstrndx")
    _, str_off, str_len = section(shstrndx)
    if str_off + str_len > size or str_len > 65536:
        raise ValueError("bad string table")
    strtab = os.pread(fd, str_len, str_off)
    out = {}
    for i in range(shnum):
        name_off, offset, length = section(i)
        name = strtab[name_off:strtab.find(b"\0", name_off)].decode("ascii", "replace")
        if name not in APPIMAGE_SECTIONS or offset + length > size or length > 65536:
            continue
        raw = os.pread(fd, length, offset).split(b"\0", 1)[0]
        if name == ".upd_info" and raw:
            out["appimage.update"] = raw.decode("utf-8", "replace")[:512]
        elif name == ".sha256_sig" and raw.strip(b"\0"):
            out["appimage.signature"] = "present"
    return out
