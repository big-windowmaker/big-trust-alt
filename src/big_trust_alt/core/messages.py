"""User-facing texts for codes produced by the detectors and the resolver."""

from __future__ import annotations

from ..i18n import _
from .model import Finding, Level, OptionKind, Relation


def finding_text(f: Finding) -> str:
    texts = {
        "deceptive-name": _("The name hides characters that change how it is displayed. "
                            "The real extension may not be the one you see."),
        "control-chars-in-name": _("The name contains invisible control characters."),
        "double-extension": _("Double extension ({detail}): a program disguised as a document?"),
        "long-name": _("Very long file name."),
        "disguised-executable": _("The extension says document, but the content is a program ({detail})."),
        "extension-mismatch": _("The extension does not match the content ({detail})."),
        "foreign-architecture": _("Built for another processor ({detail})."),
        "unsigned": _("No digital signature."),
        "signature-unverified": _("Has a digital signature; it was not verified here."),
        "requests-admin": _("Asks Windows for administrator rights when it runs."),
        "dotnet": _("Uses .NET (Mono or wine-mono needed to run it under Wine)."),
        "damaged": _("The file looks damaged or truncated ({detail})."),
        "empty-file": _("The file is empty."),
        "symlink": _("Opened through a symbolic link to {detail}."),
        "world-writable": _("Other users can change this file."),
        "third-party-remote": _("Adds packages from a third-party Flatpak remote ({detail})."),
        "jar-windows-natives": _("Contains Windows libraries: may not work on Linux."),
        "contains-windows-programs": _("Contains Windows programs: {detail}."),
        "script-download-and-run": _("Downloads and runs code from the internet."),
        "script-privilege": _("Asks for administrator rights (sudo/pkexec)."),
        "script-recursive-delete": _("Deletes folders recursively."),
        "script-disk-write": _("Writes to disks or partitions directly."),
        "script-system-files": _("Changes system files."),
        "script-world-writable": _("Makes files writable by everyone (chmod 777)."),
        "script-obfuscation": _("Contains hidden or encoded code."),
        "script-persistence": _("Configures something to start automatically."),
        "script-binary-payload": _("Carries an embedded binary payload."),
    }
    text = texts.get(f.code, f.code)
    return text.replace("{detail}", f.detail) if "{detail}" in text else text


def error_text(code: str) -> str:
    return {
        "not-found": _("The file does not exist (it may have been moved or deleted)."),
        "permission-denied": _("You do not have permission to read this file."),
        "not-regular": _("This is not a regular file (folder, device or pipe)."),
        "unreadable": _("The file could not be read."),
        "cancelled": _("Analysis cancelled."),
    }.get(code, code)


def level_text(level: Level) -> str:
    return {
        Level.CONFIRMED: _("Confirmed match"),
        Level.PROBABLE: _("Probable match"),
        Level.AMBIGUOUS: _("More than one possible program"),
        Level.UNKNOWN: _("Program not identified"),
    }[level]


def relation_text(relation: Relation) -> str:
    return {
        Relation.SAME: _("Same program"),
        Relation.SUCCESSOR: _("Successor"),
        Relation.ALTERNATIVE: _("Functional alternative"),
        Relation.WEB: _("Web version"),
        Relation.LAUNCHER: _("Game launcher"),
        Relation.COMPATIBILITY: _("Compatibility layer"),
        Relation.ORIGINAL: _("This file"),
    }[relation]


def action_text(kind: OptionKind) -> str:
    return {
        OptionKind.OPEN_INSTALLED: _("Open"),
        OptionKind.INSTALL_REPO: _("Install"),
        OptionKind.INSTALL_FLATPAK: _("Install"),
        OptionKind.INSTALL_AUR: _("Build and install"),
        OptionKind.INSTALL_PACKAGE_FILE: _("Install"),
        OptionKind.CONVERT_PACKAGE: _("Convert and install"),
        OptionKind.INSTALL_FLATPAKREF: _("Install"),
        OptionKind.OPEN_WEBSITE: _("Open website"),
        OptionKind.OPEN_STEAM: _("Open in Steam"),
        OptionKind.RUN_WINE: _("Run…"),
        OptionKind.RUN_BOTTLES: _("Open"),
        OptionKind.RUN_NATIVE: _("Run…"),
        OptionKind.RUN_JAVA: _("Run…"),
    }[kind]


PROVIDER_NAMES = {"repos": "pacman", "flatpak": "Flatpak", "aur": "AUR"}


def format_text(report) -> str:
    """Translated description of the detected format."""
    meta = report.metadata
    fmt = report.format
    if fmt == "exe":
        kind = meta.get("pe.installer")
        if meta.get("pe.type") == "dll":
            return _("Windows library (DLL)")
        if kind:
            return _("Windows installer ({builder})").format(builder=INSTALLER_NAMES.get(kind, kind))
        from ..database.normalize import normalize_filename
        words = normalize_filename(report.name).split()
        if any(w in ("setup", "installer", "install") or w.endswith("setup") for w in words):
            return _("Windows installer")
        return _("Windows program")
    if fmt == "script":
        return _("Script ({interpreter})").format(interpreter=meta.get("script.interpreter", "sh"))
    return {
        "dos": _("DOS program"),
        "msi": _("Windows Installer package (MSI)"),
        "msix": _("Windows app package (MSIX/AppX)"),
        "windows-script": _("Windows script"),
        "elf": _("Linux program"),
        "appimage": _("AppImage"),
        "deb": _("Debian/Ubuntu package (.deb)"),
        "rpm": _("Fedora/openSUSE package (.rpm)"),
        "arch-package": _("Arch Linux package"),
        "jar": _("Java application (.jar)"),
        "flatpakref": _("Flatpak reference"),
        "flatpak": _("Flatpak bundle"),
        "makeself": _("Self-extracting installer (shell)"),
        "tarball": _("Compressed archive (tar)"),
        "zip": _("ZIP archive"),
        "text": _("Text file"),
        "ole-document": _("Office/OLE document"),
    }.get(fmt, _("Unknown file"))


INSTALLER_NAMES = {"inno": "Inno Setup", "nsis": "NSIS", "installshield": "InstallShield",
                   "wix-burn": "WiX", "squirrel": "Squirrel", "7zip-sfx": "7-Zip SFX",
                   "smart-install-maker": "Smart Install Maker", "installaware": "InstallAware",
                   "setup-factory": "Setup Factory"}
