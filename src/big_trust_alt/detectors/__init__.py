"""Identify a file by its content. Never executes, extracts or modifies it."""

from __future__ import annotations

import lzma
import os
import platform as host_platform
import stat
import struct
import tarfile
import xml.etree.ElementTree as ET
import zipfile
import zlib

from ..core.model import FileReport, Platform, Severity
from ..database.normalize import KNOWN_SUFFIXES
from ..security import fileinfo
from . import archive, deb, elf, msi, pe, rpm, text

HEAD = 64 * 1024
PARSE_ERRORS = (ValueError, struct.error, OSError, EOFError, tarfile.TarError,
                zipfile.BadZipFile, lzma.LZMAError, zlib.error, ET.ParseError,
                UnicodeError, KeyError, IndexError, OverflowError, MemoryError,
                NotImplementedError, RuntimeError)
try:
    from compression import zstd as _zstd
    PARSE_ERRORS += (_zstd.ZstdError,)
except ImportError:  # pragma: no cover - Python < 3.14
    pass

# Formats that the extension promises.
EXPECTED = {
    ".exe": {"exe", "dos"}, ".msi": {"msi"}, ".msix": {"msix"}, ".appx": {"msix"},
    ".msixbundle": {"msix"}, ".appxbundle": {"msix"},
    ".deb": {"deb"}, ".rpm": {"rpm"}, ".appimage": {"appimage"}, ".jar": {"jar"},
    ".sh": {"script"}, ".run": {"elf", "script", "makeself"}, ".bin": {"elf", "script", "makeself"},
    ".flatpakref": {"flatpakref"}, ".flatpak": {"flatpak"},
    ".bat": {"windows-script"}, ".cmd": {"windows-script"}, ".ps1": {"windows-script"},
    ".pkg.tar.zst": {"arch-package"}, ".pkg.tar.xz": {"arch-package"},
    ".tar.gz": {"tarball", "arch-package"}, ".tar.xz": {"tarball", "arch-package"},
    ".tar.zst": {"tarball", "arch-package"}, ".tar.bz2": {"tarball"}, ".tgz": {"tarball"},
    ".zip": {"zip", "jar", "msix"},
}
DOCUMENT_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".odt", ".txt", ".jpg", ".jpeg",
                 ".png", ".gif", ".mp3", ".mp4", ".mkv", ".avi", ".ppt", ".pptx"}
RUNNABLE = {"exe", "dos", "msi", "elf", "appimage", "script", "makeself", "windows-script", "jar"}
_HOST_ARCH = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64",
              "arm64": "aarch64", "i686": "x86"}.get(host_platform.machine().lower(), host_platform.machine())


def declared_extension(name: str) -> str:
    lower = name.lower()
    for suffix in sorted(set(EXPECTED) | set(KNOWN_SUFFIXES) | DOCUMENT_EXTS, key=len, reverse=True):
        if lower.endswith(suffix) and len(lower) > len(suffix):
            return suffix
    return os.path.splitext(lower)[1]


def analyze_file(path: str, cancel=None, hash_file: bool = True) -> FileReport:
    name = os.path.basename(path.rstrip("/")) or path
    report = FileReport(path=path, name=name, declared_extension=declared_extension(name))
    fileinfo.check_name(report)
    try:
        fd, st, target = fileinfo.open_regular(path)
    except fileinfo.FileAccessError as exc:
        report.error = exc.code
        return report
    try:
        report.path = os.path.realpath(path)
        report.symlink_target = target
        report.size = st.st_size
        report.executable_bit = bool(st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
        head = os.pread(fd, HEAD, 0)
        _sniff(fd, st.st_size, head, report)
        _check_extension(report)
        _check_architecture(report)
        report.origin_url, report.referrer_url = fileinfo.read_origin(report.path)
        if hash_file:
            try:
                report.identity = fileinfo.identity_of(fd, st, cancel)
            except fileinfo.FileAccessError as exc:
                report.error = exc.code
        if st.st_size == 0:
            report.add("empty-file", Severity.WARNING)
        if target:
            report.add("symlink", Severity.INFO, target)
        if st.st_uid != os.getuid() and st.st_mode & stat.S_IWOTH:
            report.add("world-writable", Severity.WARNING)
    finally:
        os.close(fd)
    return report


def _sniff(fd: int, size: int, head: bytes, report: FileReport) -> None:
    meta = report.metadata
    try:
        if pe.is_pe(head):
            meta.update(pe.parse(fd, size))
            report.format = "dos" if meta.get("pe.type") == "dos" else "exe"
            report.platform = Platform.WINDOWS
            report.architecture = meta.get("pe.machine", "x86")
            kind = meta.get("pe.installer")
            if meta.get("pe.type") == "dll":
                report.format_label = "Windows library (DLL)"
            elif kind:
                report.format_label = f"Windows installer ({kind})"
            else:
                report.format_label = "Windows program"
            if meta.get("pe.dotnet"):
                report.add("dotnet", Severity.INFO)
            if meta.get("pe.requested_level") == "requireAdministrator":
                report.add("requests-admin", Severity.INFO)
            if meta.get("pe.signature") != "present":
                report.add("unsigned", Severity.WARNING)
            else:
                report.add("signature-unverified", Severity.INFO)
        elif msi.is_cfb(head):
            meta.update(msi.parse(fd, size))
            if meta.get("msi.summary") == "missing" and report.declared_extension != ".msi":
                report.format, report.format_label = "ole-document", "Office/OLE document"
                return
            report.format, report.platform = "msi", Platform.WINDOWS
            report.format_label = "Windows Installer package (MSI)"
            template = meta.get("msi.Template", "").split(";", 1)[0].lower()
            report.architecture = {"intel": "x86", "x64": "x86_64", "amd64": "x86_64",
                                   "arm64": "aarch64", "intel64": "ia64"}.get(template, template)
        elif elf.is_elf(head):
            meta.update(elf.parse(fd, size))
            report.platform = Platform.LINUX
            report.architecture = meta.get("elf.machine", "")
            if "appimage.type" in meta:
                report.format, report.format_label = "appimage", "AppImage"
                if meta.get("appimage.signature") != "present":
                    report.add("unsigned", Severity.INFO)
            else:
                report.format = "elf"
                report.format_label = "Linux program" if meta.get("elf.type") != "shared" else "Linux library or program"
        elif deb.is_deb(head):
            meta.update(deb.parse(fd, size))
            report.format, report.platform = "deb", Platform.LINUX
            report.format_label = "Debian/Ubuntu package (.deb)"
            report.architecture = _pkg_arch(meta.get("deb.Architecture", ""))
        elif rpm.is_rpm(head):
            meta.update(rpm.parse(fd, size))
            report.format, report.platform = "rpm", Platform.LINUX
            report.format_label = "Fedora/openSUSE package (.rpm)"
            report.architecture = _pkg_arch(meta.get("rpm.Arch", ""))
        elif archive.is_zip(head):
            fmt, info = archive.parse_zip(fd, size)
            meta.update(info)
            report.format = fmt
            if fmt == "jar":
                report.platform, report.architecture = Platform.JAVA, "any"
                report.format_label = "Java application (.jar)"
                if info.get("jar.native_windows"):
                    report.add("jar-windows-natives", Severity.INFO)
            elif fmt == "msix":
                report.platform = Platform.WINDOWS
                report.format_label = "Windows app package (MSIX/AppX)"
                report.architecture = _pkg_arch(info.get("msix.Architecture", "").lower())
            else:
                report.format_label = "ZIP archive"
                if info.get("zip.windows_programs"):
                    report.add("contains-windows-programs", Severity.INFO, info["zip.windows_programs"])
        elif archive.is_tar(head):
            fmt, info = archive.parse_tar(fd, size, report.name)
            meta.update(info)
            report.format = fmt
            if fmt == "arch-package":
                report.platform = Platform.LINUX
                report.format_label = "Arch Linux package"
                report.architecture = _pkg_arch(info.get("pkg.arch", ""))
            else:
                report.format_label = "Compressed archive (tar)"
        elif text.is_text(head):
            _text(head, report)
        elif report.declared_extension == ".flatpak" and head.startswith(b"flatpak"):
            report.format, report.platform = "flatpak", Platform.LINUX
            report.format_label = "Flatpak bundle"
        else:
            report.format_label = "Unknown binary file"
    except PARSE_ERRORS as exc:
        report.add("damaged", Severity.WARNING, type(exc).__name__)
        if not report.format_label:
            report.format_label = "Damaged or unsupported file"


def _text(head: bytes, report: FileReport) -> None:
    ext = report.declared_extension
    sample = head.decode("utf-8", "replace")
    if ext == ".flatpakref" or sample.lstrip().startswith("[Flatpak Ref]"):
        report.metadata.update(text.parse_flatpakref(sample))
        report.format, report.platform = "flatpakref", Platform.LINUX
        report.format_label = "Flatpak reference"
        url = report.metadata.get("flatpakref.Url", "")
        if url and fileinfo.host_of(url) not in ("dl.flathub.org", "flathub.org"):
            report.add("third-party-remote", Severity.WARNING, fileinfo.host_of(url))
        return
    shown, hints = text.preview(head)
    report.preview = shown
    if ext in (".bat", ".cmd", ".ps1"):
        report.format, report.platform = "windows-script", Platform.WINDOWS
        report.format_label = "Windows PowerShell script" if ext == ".ps1" else "Windows batch script"
        return
    interp = text.interpreter(head)
    if interp or ext in (".sh", ".run", ".bin"):
        report.platform = Platform.LINUX
        if text.is_makeself(head):
            report.format, report.format_label = "makeself", "Self-extracting installer (shell)"
        else:
            report.format, report.format_label = "script", f"Script ({interp or 'sh'})"
        report.metadata["script.interpreter"] = interp or "sh"
        for hint in hints:
            report.add(f"script-{hint}", Severity.WARNING)
        if "NVIDIA" in sample[:4096] and "driver" in sample[:4096].lower():
            report.metadata["script.vendor"] = "NVIDIA driver installer"
        return
    report.format, report.format_label = "text", "Text file"


def _pkg_arch(value: str) -> str:
    value = value.lower()
    return {"amd64": "x86_64", "x86_64": "x86_64", "x64": "x86_64", "i386": "x86", "i686": "x86",
            "x86": "x86", "arm64": "aarch64", "aarch64": "aarch64", "armhf": "arm", "armv7h": "arm",
            "all": "any", "noarch": "any", "any": "any", "neutral": "any"}.get(value, value)


def _check_extension(report: FileReport) -> None:
    ext = report.declared_extension
    fmt = report.format
    if ext in DOCUMENT_EXTS and fmt in RUNNABLE:
        report.add("disguised-executable", Severity.DANGER, f"{ext} → {fmt}")
    elif ext in EXPECTED and fmt not in EXPECTED[ext] and fmt not in ("unknown",):
        report.add("extension-mismatch", Severity.WARNING, f"{ext} → {fmt}")
    elif ext in EXPECTED and fmt == "unknown":
        report.add("extension-mismatch", Severity.WARNING, f"{ext} → ?")


def _check_architecture(report: FileReport) -> None:
    arch = report.architecture
    if not arch or arch == "any" or report.platform != Platform.LINUX:
        return
    if arch != _HOST_ARCH and not (_HOST_ARCH == "x86_64" and arch == "x86"):
        report.add("foreign-architecture", Severity.WARNING, f"{arch} ≠ {_HOST_ARCH}")
