"""Plain data shared by the detectors, the resolver, the CLI and the UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum


class Platform(StrEnum):
    WINDOWS = "windows"
    LINUX = "linux"
    JAVA = "java"
    ANY = "any"
    UNKNOWN = "unknown"


class Level(StrEnum):
    """How sure we are that a catalog entry is the program in the file."""

    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"


@dataclass(frozen=True)
class Finding:
    """Something the user should know about the file (not a verdict)."""

    code: str
    severity: Severity
    detail: str = ""


@dataclass(frozen=True)
class FileIdentity:
    """What the file was when it was analyzed; checked again before running it."""

    device: int
    inode: int
    size: int
    mtime_ns: int
    sha256: str


@dataclass
class FileReport:
    path: str
    name: str
    size: int = 0
    format: str = "unknown"          # see detectors.FORMATS
    format_label: str = ""           # human readable, e.g. "Windows installer (Inno Setup)"
    declared_extension: str = ""
    platform: Platform = Platform.UNKNOWN
    architecture: str = ""           # x86, x86_64, arm, aarch64, any …
    metadata: dict[str, str] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    identity: FileIdentity | None = None
    origin_url: str = ""
    referrer_url: str = ""
    executable_bit: bool = False
    symlink_target: str = ""
    preview: str = ""                # first lines of a script, for display only
    error: str = ""                  # set when the file could not be analyzed

    def add(self, code: str, severity: Severity = Severity.INFO, detail: str = "") -> None:
        if not any(f.code == code and f.detail == detail for f in self.findings):
            self.findings.append(Finding(code, severity, detail))

    def has(self, code: str) -> bool:
        return any(f.code == code for f in self.findings)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["findings"] = [asdict(f) for f in self.findings]
        return data


class OptionKind(StrEnum):
    OPEN_INSTALLED = "open-installed"
    INSTALL_REPO = "install-repo"
    INSTALL_FLATPAK = "install-flatpak"
    INSTALL_AUR = "install-aur"
    INSTALL_PACKAGE_FILE = "install-package-file"   # .pkg.tar.* through Pamac
    CONVERT_PACKAGE = "convert-package"             # .deb/.rpm through big-pkg-installer
    INSTALL_FLATPAKREF = "install-flatpakref"
    OPEN_WEBSITE = "open-website"
    OPEN_STEAM = "open-steam"
    RUN_WINE = "run-wine"
    RUN_BOTTLES = "run-bottles"
    RUN_NATIVE = "run-native"
    RUN_JAVA = "run-java"


class Relation(StrEnum):
    SAME = "same"                  # the same program, packaged for Linux
    SUCCESSOR = "successor"
    ALTERNATIVE = "alternative"    # a different program with similar purpose
    WEB = "web"
    LAUNCHER = "launcher"
    COMPATIBILITY = "compatibility"  # run the original file (Wine, Bottles)
    ORIGINAL = "original"          # run the original Linux file itself


@dataclass
class Option:
    kind: OptionKind
    relation: Relation
    app_id: str                     # catalog id ("" for the original file)
    title: str
    target: str                     # package name, flatpak id, desktop id, URL, path …
    source_label: str = ""          # "BigLinux repositories", "Flathub", "AUR" …
    note: str = ""
    available: bool = True
    unavailable_reason: str = ""
    experimental: bool = False
    icon: str = ""
    rank: int = 1000                # lower is better
    command: list[str] = field(default_factory=list)  # shown in advanced mode

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Candidate:
    entry_id: str
    name: str
    score: int
    reasons: list[str]


@dataclass
class Analysis:
    report: FileReport
    level: Level
    candidates: list[Candidate] = field(default_factory=list)
    options: list[Option] = field(default_factory=list)
    recommended: Option | None = None
    message: str = ""
    providers_offline: list[str] = field(default_factory=list)

    @property
    def entry_id(self) -> str:
        return self.candidates[0].entry_id if self.level in (Level.CONFIRMED, Level.PROBABLE) else ""

    def to_dict(self) -> dict:
        return {
            "file": self.report.to_dict(),
            "level": str(self.level),
            "candidates": [asdict(c) for c in self.candidates],
            "recommended": self.recommended.to_dict() if self.recommended else None,
            "options": [o.to_dict() for o in self.options],
            "message": self.message,
            "providers_offline": self.providers_offline,
        }
