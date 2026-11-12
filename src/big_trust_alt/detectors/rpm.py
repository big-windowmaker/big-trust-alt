"""RPM package reader: name, version, summary from the main header."""

from __future__ import annotations

import os
import struct

LEAD_MAGIC = b"\xed\xab\xee\xdb"
HEADER_MAGIC = b"\x8e\xad\xe8\x01"
TAGS = {1000: "Name", 1001: "Version", 1002: "Release", 1004: "Summary",
        1011: "Vendor", 1020: "URL", 1022: "Arch"}
MAX_INDEX = 4096
MAX_STORE = 16 << 20


def is_rpm(head: bytes) -> bool:
    return head[:4] == LEAD_MAGIC


def _header(fd: int, offset: int, size: int):
    hdr = os.pread(fd, 16, offset)
    if len(hdr) < 16 or hdr[:4] != HEADER_MAGIC:
        raise ValueError("bad rpm header")
    nindex, hsize = struct.unpack(">II", hdr[8:16])
    if nindex > MAX_INDEX or hsize > MAX_STORE or offset + 16 + nindex * 16 + hsize > size:
        raise ValueError("rpm header too large")
    index = os.pread(fd, nindex * 16, offset + 16)
    store = os.pread(fd, hsize, offset + 16 + nindex * 16)
    return nindex, hsize, index, store


def parse(fd: int, size: int) -> dict[str, str]:
    # Lead (96 bytes), signature header padded to 8 bytes, then the main header.
    nindex, hsize, _, _ = _header(fd, 96, size)
    sig_len = 16 + nindex * 16 + hsize
    main = 96 + sig_len + (-sig_len % 8)
    nindex, _, index, store = _header(fd, main, size)
    info = {}
    for i in range(nindex):
        tag, typ, off, count = struct.unpack_from(">IIII", index, i * 16)
        if tag not in TAGS or typ not in (6, 8, 9) or off >= len(store):
            continue
        value = store[off:store.find(b"\0", off)].decode("utf-8", "replace").strip()
        if value:
            info[f"rpm.{TAGS[tag]}"] = value[:300]
    return info
