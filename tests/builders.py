"""Build small, valid sample files in memory (no binaries in the repository)."""

from __future__ import annotations

import io
import struct
import tarfile
import time


# -- Windows PE with a VS_VERSIONINFO resource --------------------------------------------
def _align(data: bytes, n: int = 4) -> bytes:
    return data + b"\0" * (-len(data) % n)


def _block(key: str, value: bytes = b"", vtype: int = 0, children: list[bytes] = (), vlen: int | None = None) -> bytes:
    body = _align(struct.pack("<HHH", 0, 0, 0) + (key + "\0").encode("utf-16-le"))
    body = _align(body + value)
    for child in children:
        body = _align(body + child)
    length = len(body)
    value_len = vlen if vlen is not None else len(value)
    return struct.pack("<HHH", length, value_len, vtype) + body[6:]


def version_info(strings: dict[str, str]) -> bytes:
    items = [_block(k, (v + "\0").encode("utf-16-le"), 1, vlen=len(v) + 1) for k, v in strings.items()]
    table = _block("040904b0", children=items, vtype=1)
    sfi = _block("StringFileInfo", children=[table], vtype=1)
    fixed = struct.pack("<13I", 0xFEEF04BD, 0x10000, *([0] * 11))
    return _block("VS_VERSION_INFO", fixed, 0, [sfi])


def build_pe(strings: dict[str, str] | None = None, machine: int = 0x14C, signed: bool = False,
             dotnet: bool = False, manifest: bytes | None = None, payload: bytes = b"") -> bytes:
    rsrc = bytearray()
    resources = []
    if strings is not None:
        resources.append((16, version_info(strings)))
    if manifest is not None:
        resources.append((24, manifest))
    # Resource tree: root -> type -> name(1) -> lang(0x409) -> data entry.
    n = len(resources)
    root_size = 16 + 8 * n
    layout = []
    offset = root_size
    for _ in resources:
        layout.append(offset)  # name dir, lang dir, data entry
        offset += (16 + 8) * 2 + 16
    data_offsets = []
    for _, blob in resources:
        data_offsets.append(offset)
        offset += len(blob) + (-len(blob) % 4)
    rsrc += struct.pack("<IIHHHH", 0, 0, 0, 0, 0, n)
    for (rtype, _), base in zip(resources, layout):
        rsrc += struct.pack("<II", rtype, 0x80000000 | base)
    for (_, blob), base, doff in zip(resources, layout, data_offsets):
        rsrc += struct.pack("<IIHHHH", 0, 0, 0, 0, 0, 1) + struct.pack("<II", 1, 0x80000000 | (base + 24))
        rsrc += struct.pack("<IIHHHH", 0, 0, 0, 0, 0, 1) + struct.pack("<II", 0x409, base + 48)
        rsrc += struct.pack("<IIII", 0x1000 + doff, len(blob), 0, 0)
    for _, blob in resources:
        rsrc += blob + b"\0" * (-len(blob) % 4)
    rsrc = bytes(rsrc) + b"\0" * (-len(rsrc) % 0x200)

    dos = bytearray(0x80)
    dos[0:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, 0x80)
    coff = struct.pack("<HHIIIHH", machine, 1, int(time.time()), 0, 0, 224, 0x0102)
    opt = bytearray(224)
    struct.pack_into("<H", opt, 0, 0x10B)
    struct.pack_into("<H", opt, 68, 2)
    struct.pack_into("<I", opt, 92, 16)
    struct.pack_into("<II", opt, 96 + 8 * 2, 0x1000, len(rsrc))
    if dotnet:
        struct.pack_into("<II", opt, 96 + 8 * 14, 0x1000, 72)
    section = struct.pack("<8sIIIIIIHHI", b".rsrc", len(rsrc), 0x1000, len(rsrc), 0x200, 0, 0, 0, 0, 0x40000040)
    headers = bytes(dos) + b"PE\0\0" + coff + bytes(opt) + section
    image = headers + b"\0" * (0x200 - len(headers)) + rsrc + payload
    if signed:
        cert = struct.pack("<IHH", 16, 0x200, 2) + b"\x30\x82\0\0" * 1
        opt_off = 0x80 + 24
        image = bytearray(image)
        struct.pack_into("<II", image, opt_off + 96 + 8 * 4, len(image), len(cert))
        image = bytes(image) + cert
    return image


# -- MSI (compound file with a SummaryInformation stream) --------------------------------------
def summary_stream(props: dict[int, str]) -> bytes:
    values = b""
    entries = []
    base = 8 + 8 * len(props)
    for pid, text in props.items():
        raw = text.encode("cp1252") + b"\0"
        entries.append((pid, base + len(values)))
        values += _align(struct.pack("<II", 0x1E, len(raw)) + raw)
    section = struct.pack("<II", base + len(values), len(props))
    section += b"".join(struct.pack("<II", pid, off) for pid, off in entries) + values
    header = struct.pack("<HHI16sI", 0xFFFE, 0, 0x20006, b"\0" * 16, 1) + b"\xe0\x85\x9f\xf2" + b"\0" * 12
    header += struct.pack("<I", 48)
    return header + section


def build_msi(subject: str, author: str, template: str = "x64;1033") -> bytes:
    stream = summary_stream({3: subject, 4: author, 7: template})
    sector = 512
    hdr = bytearray(512)
    hdr[0:8] = bytes.fromhex("D0CF11E0A1B11AE1")
    struct.pack_into("<HHHH", hdr, 0x18, 0x3E, 3, 0xFFFE, 9)
    struct.pack_into("<H", hdr, 0x20, 6)
    struct.pack_into("<I", hdr, 0x2C, 1)          # FAT sectors
    struct.pack_into("<I", hdr, 0x30, 1)          # first directory sector
    struct.pack_into("<I", hdr, 0x38, 0)          # mini stream cutoff 0: regular stream
    struct.pack_into("<I", hdr, 0x3C, 0xFFFFFFFE)
    struct.pack_into("<II", hdr, 0x44, 0xFFFFFFFE, 0)
    difat = [0] + [0xFFFFFFFF] * 108
    struct.pack_into("<109I", hdr, 0x4C, *difat)
    nstream = -(-len(stream) // sector)
    fat = [0xFFFFFFFD, 0xFFFFFFFE] + [3 + i for i in range(nstream - 1)] + [0xFFFFFFFE]
    fat += [0xFFFFFFFF] * (sector // 4 - len(fat))
    fat_sector = struct.pack(f"<{sector // 4}I", *fat)

    def dirent(name: str, kind: int, start: int, size: int) -> bytes:
        e = bytearray(128)
        raw = (name + "\0").encode("utf-16-le")
        e[0:len(raw)] = raw
        struct.pack_into("<H", e, 64, len(raw))
        e[66] = kind
        struct.pack_into("<III", e, 68, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF)
        struct.pack_into("<IQ", e, 0x74, start, size)
        return bytes(e)

    directory = dirent("Root Entry", 5, 0xFFFFFFFE, 0) + dirent("\x05SummaryInformation", 2, 2, len(stream))
    directory += b"\0" * (sector - len(directory))
    body = stream + b"\0" * (-len(stream) % sector)
    return bytes(hdr) + fat_sector + directory + body


# -- Debian package --------------------------------------------------------------------
def _tar(files: dict[str, bytes], mode: str = "w:gz") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode=mode) as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _ar_member(name: str, data: bytes) -> bytes:
    hdr = f"{name:<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(data):<10}`\n".encode()
    return hdr + data + (b"\n" if len(data) % 2 else b"")


def build_deb(package: str, version: str = "1.0", arch: str = "amd64", description: str = "test") -> bytes:
    control = (f"Package: {package}\nVersion: {version}\nArchitecture: {arch}\n"
               f"Maintainer: Test <t@example.org>\nDescription: {description}\n").encode()
    return (b"!<arch>\n" + _ar_member("debian-binary", b"2.0\n")
            + _ar_member("control.tar.gz", _tar({"./control": control}))
            + _ar_member("data.tar.gz", _tar({"./usr/bin/x": b"#!/bin/sh\n"})))


# -- RPM --------------------------------------------------------------------------------
def build_rpm(name: str, version: str = "1.0", summary: str = "test", arch: str = "x86_64") -> bytes:
    lead = b"\xed\xab\xee\xdb\x03\x00" + b"\0" * 90
    sig = b"\x8e\xad\xe8\x01" + b"\0" * 4 + struct.pack(">II", 0, 0)
    tags = [(1000, 6, name), (1001, 6, version), (1004, 9, summary), (1022, 6, arch)]
    store, index = b"", b""
    for tag, typ, value in tags:
        index += struct.pack(">IIII", tag, typ, len(store), 1)
        store += value.encode() + b"\0"
    main = b"\x8e\xad\xe8\x01" + b"\0" * 4 + struct.pack(">II", len(tags), len(store)) + index + store
    return lead + sig + main + b"payload"


# -- AppImage (ELF64 with AI\x02 and an .upd_info section) --------------------------------------
def build_appimage(update: str = "gh-releases-zsync|owner|repo|latest|App-*x86_64.AppImage.zsync",
                   machine: int = 0x3E) -> bytes:
    shstr = b"\0.shstrtab\0.upd_info\0"
    upd = update.encode() + b"\0"
    data_off = 64
    shstr_off = data_off
    upd_off = shstr_off + len(shstr)
    shoff = upd_off + len(upd)
    shoff += -shoff % 8
    ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"AI\x02" + b"\0" * 5
    header = ident + struct.pack("<HHIQQQIHHHHHH", 2, machine, 1, 0, 0, shoff, 0, 64, 56, 0, 64, 3, 1)

    def sh(name, offset, size):
        return struct.pack("<IIQQQQIIQQ", name, 1, 0, 0, offset, size, 0, 0, 1, 0)

    sections = sh(0, 0, 0) + sh(1, shstr_off, len(shstr)) + sh(11, upd_off, len(upd))
    body = header + shstr + upd
    body += b"\0" * (shoff - len(body))
    return body + sections


def build_pkg(pkgname: str, pkgver: str = "1.0-1") -> bytes:
    pkginfo = f"pkgname = {pkgname}\npkgver = {pkgver}\npkgdesc = test\narch = x86_64\n".encode()
    return _tar({".PKGINFO": pkginfo, "usr/bin/x": b"x"}, mode="w:xz")


def build_jar(title: str, main: str = "org.example.Main") -> bytes:
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("META-INF/MANIFEST.MF", f"Manifest-Version: 1.0\nMain-Class: {main}\n"
                                            f"Implementation-Title: {title}\n")
        zf.writestr("org/example/Main.class", b"\xca\xfe\xba\xbe")
    return buf.getvalue()


def build_msix(name: str, display: str, publisher: str = "CN=Example Corp") -> bytes:
    import zipfile
    manifest = (f'<?xml version="1.0"?><Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10">'
                f'<Identity Name="{name}" Publisher="{publisher}" Version="1.0.0.0" ProcessorArchitecture="x64"/>'
                f'<Properties><DisplayName>{display}</DisplayName><PublisherDisplayName>Example</PublisherDisplayName>'
                f'</Properties></Package>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("AppxManifest.xml", manifest)
    return buf.getvalue()
