"""Read-only views of what the system has and what it can install.

Each provider answers from local data (pacman sync databases, Flatpak's
cached appstream, .desktop files) except the AUR, which needs the network
and is queried separately so the rest keeps working offline.
Commands run with argument lists and LC_ALL=C; never through a shell.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

AUR_RPC = "https://aur.archlinux.org/rpc/v5/info"
USER_AGENT = "big-trust-alt (+https://github.com/big-windowmaker/big-trust-alt)"


class ProviderUnavailable(Exception):
    """The provider cannot answer (tool missing, offline, timeout)."""


def run(cmd: list[str], timeout: float = 15) -> str:
    env = dict(os.environ, LC_ALL="C", LANG="C")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env,
                              stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProviderUnavailable(f"{cmd[0]}: {exc}") from None
    if proc.returncode != 0:
        raise ProviderUnavailable(f"{cmd[0]} exited with {proc.returncode}")
    return proc.stdout


@dataclass(frozen=True)
class RepoPackage:
    name: str
    repo: str
    version: str
    installed: bool


class Repos:
    """pacman sync databases (the BigLinux/Manjaro/Arch repositories)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sync: dict[str, RepoPackage] | None = None
        self._local: set[str] | None = None

    def available(self) -> bool:
        return shutil.which("pacman") is not None

    def _load(self) -> None:
        with self._lock:
            if self._sync is not None:
                return
            if not self.available():
                raise ProviderUnavailable("pacman not found")
            local = set(run(["pacman", "-Qq"]).split())
            sync = {}
            for line in run(["pacman", "-Sl"], timeout=30).splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[1] not in sync:
                    sync[parts[1]] = RepoPackage(parts[1], parts[0], parts[2], parts[1] in local)
            self._sync, self._local = sync, local

    def get(self, name: str) -> RepoPackage | None:
        self._load()
        return self._sync.get(name)

    def installed(self, name: str) -> bool:
        self._load()
        return name in self._local

    def refresh_installed(self) -> None:
        with self._lock:
            self._sync = self._local = None


@dataclass(frozen=True)
class AurPackage:
    name: str
    version: str
    votes: int
    popularity: float
    maintainer: str
    out_of_date: bool
    url: str


class Aur:
    """AUR RPC (network). Results are cached for the life of the process."""

    def __init__(self, timeout: float = 8) -> None:
        self.timeout = timeout
        self._cache: dict[str, AurPackage | None] = {}

    def info(self, names: list[str]) -> dict[str, AurPackage | None]:
        missing = [n for n in names if n not in self._cache]
        if missing:
            query = urllib.parse.urlencode([("arg[]", n) for n in missing[:100]])
            req = urllib.request.Request(f"{AUR_RPC}?{query}", headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read(4 << 20))
            except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
                raise ProviderUnavailable(f"AUR: {exc}") from None
            found = {}
            for item in data.get("results", []):
                found[item.get("Name")] = AurPackage(
                    item.get("Name", ""), str(item.get("Version", "")), int(item.get("NumVotes") or 0),
                    float(item.get("Popularity") or 0), item.get("Maintainer") or "",
                    bool(item.get("OutOfDate")), item.get("URL") or "")
            for name in missing:
                self._cache[name] = found.get(name)
        return {n: self._cache.get(n) for n in names}


class Flatpak:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._remote: dict[str, str] | None = None
        self._installed: set[str] | None = None
        self._remote_failed = False

    def available(self) -> bool:
        return shutil.which("flatpak") is not None

    def _load(self) -> None:
        with self._lock:
            if self._remote is not None:
                return
            if not self.available():
                raise ProviderUnavailable("flatpak not installed")
            remote: dict[str, str] = {}
            answered = False
            for scope in ("--system", "--user"):
                try:
                    remotes = run(["flatpak", "remotes", scope, "--columns=name"]).split()
                except ProviderUnavailable:
                    continue
                if not remotes:
                    continue
                # The cached summary lives in the user's cache; a new user (or an
                # emptied ~/.cache) has none yet, so fall back to fetching it.
                for cmd in (["flatpak", "remote-ls", scope, "--cached", "--app", "--columns=application,origin"],
                            ["flatpak", "remote-ls", scope, "--app", "--columns=application,origin"]):
                    try:
                        out = run(cmd, timeout=30)
                    except ProviderUnavailable:
                        continue
                    answered = True
                    for line in out.splitlines():
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            remote.setdefault(parts[0].strip(), parts[1].strip())
                    break
            self._remote_failed = not answered
            try:
                installed = set(run(["flatpak", "list", "--app", "--columns=application"]).split())
            except ProviderUnavailable:
                installed = set()
            self._remote, self._installed = remote, installed

    def remote_of(self, app_id: str) -> str:
        """Remote that offers app_id ("" if none); raises if no remote could be read."""
        self._load()
        if self._remote_failed:
            raise ProviderUnavailable("flatpak remotes could not be listed")
        return self._remote.get(app_id, "")

    def installed(self, app_id: str) -> bool:
        self._load()
        return app_id in self._installed

    def refresh(self) -> None:
        with self._lock:
            self._remote = self._installed = None


@dataclass(frozen=True)
class DesktopApp:
    desktop_id: str
    name: str
    icon: str
    path: str


class Desktop:
    """Installed applications, found through their .desktop files (XDG)."""

    def dirs(self) -> list[Path]:
        home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        system = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
        bases = [home, *system.split(":"),
                 os.path.expanduser("~/.local/share/flatpak/exports/share"),
                 "/var/lib/flatpak/exports/share"]
        seen, out = set(), []
        for base in bases:
            path = Path(base) / "applications"
            if base and path.is_dir() and path not in seen:
                seen.add(path)
                out.append(path)
        return out

    def find(self, desktop_id: str) -> DesktopApp | None:
        for directory in self.dirs():
            path = directory / desktop_id
            if path.is_file():
                fields = _desktop_fields(path)
                if fields.get("Hidden") == "true" or fields.get("Type", "Application") != "Application":
                    continue
                return DesktopApp(desktop_id, fields.get("Name", desktop_id[:-8]), fields.get("Icon", ""), str(path))
        return None


def _desktop_fields(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            in_entry = False
            for line in fh:
                line = line.strip()
                if line.startswith("["):
                    if in_entry:
                        break
                    in_entry = line == "[Desktop Entry]"
                elif in_entry and "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    if key in ("Name", "Icon", "Hidden", "Type", "NoDisplay", "Exec"):
                        fields.setdefault(key, value)
    except OSError:
        pass
    return fields


class Tools:
    """Programs the options depend on."""

    def which(self, name: str) -> str:
        return shutil.which(name) or ""

    @property
    def wine(self) -> str:
        return self.which("wine")

    @property
    def big_pkg_installer(self) -> str:
        return self.which("big-pkg-installer-gui")

    @property
    def pamac_installer(self) -> str:
        return self.which("pamac-installer")

    @property
    def java(self) -> str:
        return self.which("java")

    @property
    def steam(self) -> str:
        return self.which("steam")


class System:
    """Bundle of providers; one per process, shared by the resolver and the UI."""

    def __init__(self) -> None:
        self.repos = Repos()
        self.aur = Aur()
        self.flatpak = Flatpak()
        self.desktop = Desktop()
        self.tools = Tools()
