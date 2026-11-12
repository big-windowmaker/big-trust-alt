"""Minimal OLE compound file reader for the MSI SummaryInformation stream.

Gives the product name (Subject), the manufacturer (Author) and the
platform (Template, e.g. "x64;1033"). Bounded: at most MAX_SECTORS sectors
are followed in any chain, so loops and huge files cannot hang it.
"""

from __future__ import annotations

import os
import struct

MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
MAX_SECTORS = 1 << 16
MAX_STREAM = 1 << 20
ENDOFCHAIN = 0xFFFFFFFE
FREESECT = 0xFFFFFFFF
SUMMARY = "\x05SummaryInformation"
PIDS = {2: "Title", 3: "Subject", 4: "Author", 5: "Keywords", 6: "Comments", 7: "Template"}


def is_cfb(head: bytes) -> bool:
    return head[:8] == MAGIC


class _CFB:
    def __init__(self, fd: int, size: int) -> None:
        self.fd, self.size = fd, size
        hdr = os.pread(fd, 512, 0)
        if len(hdr) < 512 or hdr[:8] != MAGIC:
            raise ValueError("not a compound file")
        shift, mini_shift = struct.unpack_from("<HH", hdr, 0x1E)
        if shift not in (9, 12) or mini_shift != 6:
            raise ValueError("unsupported sector size")
        self.sector = 1 << shift
        self.mini = 1 << mini_shift
        (nfat,) = struct.unpack_from("<I", hdr, 0x2C)
        (self.dir_start,) = struct.unpack_from("<I", hdr, 0x30)
        (self.cutoff,) = struct.unpack_from("<I", hdr, 0x38)
        (self.minifat_start,) = struct.unpack_from("<I", hdr, 0x3C)
        (difat_start, ndifat) = struct.unpack_from("<II", hdr, 0x44)
        difat = list(struct.unpack_from("<109I", hdr, 0x4C))
        nxt, guard = difat_start, 0
        per = self.sector // 4 - 1
        while nxt not in (ENDOFCHAIN, FREESECT) and guard < ndifat and guard < 1024:
            data = self._sector(nxt)
            values = struct.unpack_from(f"<{per + 1}I", data)
            difat.extend(values[:per])
            nxt = values[per]
            guard += 1
        fat_sectors = [s for s in difat if s not in (ENDOFCHAIN, FREESECT)][: min(nfat, 4096)]
        self.fat: list[int] = []
        for s in fat_sectors:
            self.fat.extend(struct.unpack_from(f"<{self.sector // 4}I", self._sector(s)))
            if len(self.fat) > MAX_SECTORS * 4:
                break

    def _sector(self, index: int) -> bytes:
        offset = (index + 1) * self.sector
        if offset + self.sector > self.size:
            raise ValueError("sector out of bounds")
        return os.pread(self.fd, self.sector, offset)

    def _chain(self, start: int, fat: list[int]) -> list[int]:
        chain, seen = [], set()
        while start not in (ENDOFCHAIN, FREESECT):
            if start in seen or start >= len(fat) or len(chain) >= MAX_SECTORS:
                raise ValueError("bad sector chain")
            seen.add(start)
            chain.append(start)
            start = fat[start]
        return chain

    def _read_chain(self, start: int, limit: int) -> bytes:
        out = bytearray()
        for s in self._chain(start, self.fat):
            out += self._sector(s)
            if len(out) >= limit:
                break
        return bytes(out[:limit])

    def summary_stream(self) -> bytes | None:
        directory = self._read_chain(self.dir_start, 128 * 4096)
        root_start = root_size = None
        target = None
        for off in range(0, len(directory) - 127, 128):
            entry = directory[off:off + 128]
            (name_len,) = struct.unpack_from("<H", entry, 64)
            kind = entry[66]
            if not 2 <= name_len <= 64 or kind == 0:
                continue
            name = entry[: name_len - 2].decode("utf-16-le", "replace")
            start, size = struct.unpack_from("<IQ", entry, 0x74)
            if kind == 5:
                root_start, root_size = start, size
            elif name == SUMMARY and kind == 2:
                target = (start, size)
        if target is None:
            return None
        start, size = target
        size = min(size, MAX_STREAM)
        if size >= self.cutoff:
            return self._read_chain(start, size)
        if root_start is None:
            return None
        ministream = self._read_chain(root_start, min(root_size or 0, 64 << 20))
        minifat = []
        for s in self._chain(self.minifat_start, self.fat):
            minifat.extend(struct.unpack_from(f"<{self.sector // 4}I", self._sector(s)))
        out = bytearray()
        for s in self._chain(start, minifat):
            out += ministream[s * self.mini:(s + 1) * self.mini]
            if len(out) >= size:
                break
        return bytes(out[:size])


def parse(fd: int, size: int) -> dict[str, str]:
    stream = _CFB(fd, size).summary_stream()
    if not stream:
        return {"msi.summary": "missing"}
    return parse_summary(stream)


def parse_summary(stream: bytes) -> dict[str, str]:
    info: dict[str, str] = {}
    if len(stream) < 48 or stream[:2] != b"\xfe\xff":
        return info
    (section_offset,) = struct.unpack_from("<I", stream, 44)
    if section_offset + 8 > len(stream):
        return info
    _, count = struct.unpack_from("<II", stream, section_offset)
    codepage = "cp1252"
    props = []
    for i in range(min(count, 64)):
        pos = section_offset + 8 + 8 * i
        if pos + 8 > len(stream):
            break
        pid, off = struct.unpack_from("<II", stream, pos)
        props.append((pid, section_offset + off))
    for pid, pos in props:
        if pid == 1 and pos + 8 <= len(stream):
            vtype, value = struct.unpack_from("<IH", stream, pos)
            if vtype == 2 and value not in (0, 1200):
                codepage = "utf-8" if value == 65001 else f"cp{value}"
    for pid, pos in props:
        if pid not in PIDS or pos + 8 > len(stream):
            continue
        vtype, length = struct.unpack_from("<II", stream, pos)
        if vtype != 0x1E or length > 4096:
            continue
        raw = stream[pos + 8:pos + 8 + length].split(b"\0", 1)[0]
        try:
            text = raw.decode(codepage, "replace")
        except LookupError:
            text = raw.decode("cp1252", "replace")
        if text.strip():
            info[f"msi.{PIDS[pid]}"] = text.strip()[:200]
    return info
