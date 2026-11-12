"""Turn a FileReport into an Analysis: who the program is and what to do with it.

The resolver only reads: it never installs, launches or executes anything.
Ranks (lower is better) implement the default preference order:

  0 open installed copy · 10 repository · 20 Flathub · 30 Steam · 40 AUR
  45 Arch package file · 50 .deb/.rpm through big-pkg-installer · 60 official site
  100+ functional alternatives · 200 Wine / Bottles · 300 run the original Linux file
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.model import (Analysis, FileReport, Level, Option, OptionKind, Platform,
                          Relation)
from ..database.catalog import Catalog
from ..i18n import _, pick
from ..providers import ProviderUnavailable, System
from .matcher import Index, classify

WINDOWS_FORMATS = {"exe", "msi", "windows-script"}
NATIVE_RUNNABLE = {"appimage", "elf", "script", "makeself"}


@dataclass
class Preferences:
    prefer_flatpak: bool = False
    show_aur: bool = True
    query_aur: bool = True


class Resolver:
    def __init__(self, catalog: Catalog, system: System | None = None,
                 prefs: Preferences | None = None) -> None:
        self.catalog = catalog
        self.index = Index(catalog)
        self.system = system or System()
        self.prefs = prefs or Preferences()

    # -- identification -------------------------------------------------
    def analyze(self, report: FileReport, chosen: str | None = None) -> Analysis:
        candidates = self.index.candidates(report) if not report.error else []
        level = classify(candidates)
        analysis = Analysis(report=report, level=level, candidates=candidates)
        if report.error:
            return analysis
        offline: set[str] = set()
        entry = None
        if chosen and chosen in self.catalog.entries:
            entry = self.catalog.entries[chosen]
            analysis.level = Level.CONFIRMED if any(c.entry_id == chosen and c.score >= 80
                                                    for c in candidates) else Level.PROBABLE
            analysis.candidates = [c for c in candidates if c.entry_id == chosen] or candidates
        elif level in (Level.CONFIRMED, Level.PROBABLE):
            entry = self.catalog.entries[candidates[0].entry_id]

        options: list[Option] = []
        if entry is not None:
            analysis.message = pick(entry.get("message"))
            options += self.app_options(entry, Relation.SAME, offline)
            for alt in entry.get("alternatives", ()):
                target = self.catalog.get(alt["id"])
                if target is None:
                    continue
                relation = Relation(alt["relation"])
                for opt in self.app_options(target, relation, offline, best_only=True,
                                            note=pick(alt.get("note"))):
                    options.append(opt)
        options += self.file_options(report, entry)
        options = self._dedupe(options)
        options.sort(key=lambda o: (not o.available, o.rank, o.title))
        analysis.options = options
        analysis.recommended = self._recommend(options)
        analysis.providers_offline = sorted(offline)
        return analysis

    def search(self, text: str) -> list[dict]:
        return self.catalog.search(text)

    def entry_analysis(self, entry_id: str) -> list[Option]:
        """Options for a catalog entry without a file (search page)."""
        entry = self.catalog.entries[entry_id]
        offline: set[str] = set()
        options = self.app_options(entry, Relation.SAME, offline)
        for alt in entry.get("alternatives", ()):
            target = self.catalog.get(alt["id"])
            if target:
                options += self.app_options(target, Relation(alt["relation"]), offline,
                                            best_only=True, note=pick(alt.get("note")))
        options = self._dedupe(options)
        options.sort(key=lambda o: (not o.available, o.rank, o.title))
        return options

    # -- options for a catalog entry ------------------------------------
    def app_options(self, entry: dict, relation: Relation, offline: set[str],
                    best_only: bool = False, note: str = "") -> list[Option]:
        linux = entry.get("linux", {})
        base = 0 if relation == Relation.SAME else 100
        if relation == Relation.SUCCESSOR:
            base = 5
        name = entry["name"]
        icon = _icon_for(entry)
        opts: list[Option] = []

        def make(kind, rank, target, source, **kw) -> Option:
            return Option(kind=kind, relation=relation, app_id=entry["id"], title=name,
                          target=target, source_label=source, note=kw.pop("note", note),
                          icon=icon, rank=base + rank, **kw)

        # Already installed?
        installed = False
        for desktop_id in linux.get("desktop", ()):
            app = self.system.desktop.find(desktop_id)
            if app:
                opts.append(make(OptionKind.OPEN_INSTALLED, 0, desktop_id, _("Installed on this computer"),
                                 command=["gtk-launch", desktop_id[:-8]]))
                installed = True
                break
        if not installed:
            for app_id in linux.get("flatpak", ()):
                try:
                    if self.system.flatpak.installed(app_id):
                        opts.append(make(OptionKind.OPEN_INSTALLED, 0, f"{app_id}.desktop",
                                         _("Installed on this computer (Flatpak)"),
                                         command=["flatpak", "run", app_id]))
                        installed = True
                        break
                except ProviderUnavailable:
                    break
        if installed and best_only:
            return opts

        flat_rank, repo_rank = (10, 20) if self.prefs.prefer_flatpak else (20, 10)
        aur_names = []
        for pkg in linux.get("packages", ()):
            try:
                info = self.system.repos.get(pkg)
            except ProviderUnavailable:
                offline.add("repos")
                break
            if info:
                if info.installed and not installed:
                    # Installed but no launcher found (CLI program or renamed .desktop).
                    opts.append(make(OptionKind.OPEN_INSTALLED, 0, pkg, _("Installed on this computer"),
                                     available=False,
                                     unavailable_reason=_("Already installed. It has no menu entry: use it from "
                                                          "the terminal or from other programs.")))
                    installed = True
                elif not info.installed:
                    opts.append(make(OptionKind.INSTALL_REPO, repo_rank, pkg,
                                     _("BigLinux repositories ({repo})").format(repo=info.repo),
                                     command=["pamac-installer", pkg]))
            else:
                aur_names.append(pkg)

        for app_id in linux.get("flatpak", ()):
            try:
                remote = self.system.flatpak.remote_of(app_id)
            except ProviderUnavailable:
                if self.system.flatpak.available():
                    offline.add("flatpak")
                else:
                    opts.append(make(OptionKind.INSTALL_FLATPAK, flat_rank, app_id, "Flathub",
                                     available=False,
                                     unavailable_reason=_("Flatpak is not installed on this system.")))
                break
            if remote and not installed:
                opts.append(make(OptionKind.INSTALL_FLATPAK, flat_rank, app_id,
                                 "Flathub" if remote == "flathub" else remote,
                                 command=["flatpak", "install", "--system", "-y", remote, app_id]))

        if linux.get("steam") and not installed:
            available = bool(self.system.tools.steam)
            opts.append(make(OptionKind.OPEN_STEAM, 30, linux["steam"], "Steam",
                             available=available,
                             unavailable_reason="" if available else _("Steam is not installed."),
                             command=["xdg-open", f"steam://store/{linux['steam']}"]))

        if aur_names and self.prefs.show_aur and not installed:
            if self.prefs.query_aur:
                try:
                    found = self.system.aur.info(aur_names)
                except ProviderUnavailable:
                    offline.add("aur")
                    found = {}
                for pkg in aur_names:
                    info = found.get(pkg)
                    if info is None:
                        continue
                    detail = _("Community package: its build script is not reviewed by BigLinux. "
                               "Read it before building.")
                    if info.out_of_date:
                        detail += " " + _("Marked out of date.")
                    if not info.maintainer:
                        detail += " " + _("Without a maintainer.")
                    opts.append(make(OptionKind.INSTALL_AUR, 40, pkg, "AUR",
                                     note=detail if relation == Relation.SAME else note,
                                     experimental=info.out_of_date or not info.maintainer,
                                     command=["pamac-installer", "--build", pkg]))

        site = linux.get("website") or linux.get("instructions")
        if site and not installed:
            label = _("Official website") if linux.get("website") else _("Installation instructions")
            opts.append(make(OptionKind.OPEN_WEBSITE, 60, site, label, command=["xdg-open", site]))

        if best_only and opts:
            opts.sort(key=lambda o: (not o.available, o.rank))
            return opts[:1]
        return opts

    # -- options for the file itself -------------------------------------
    def file_options(self, report: FileReport, entry: dict | None) -> list[Option]:
        opts: list[Option] = []
        fmt, path = report.format, report.path
        tools = self.system.tools
        title = report.name

        def make(kind, relation, rank, source, **kw) -> Option:
            return Option(kind=kind, relation=relation, app_id="", title=kw.pop("title", title),
                          target=path, source_label=source, rank=rank, **kw)

        if fmt in ("deb", "rpm"):
            ok = bool(tools.big_pkg_installer)
            opts.append(make(OptionKind.CONVERT_PACKAGE, Relation.ORIGINAL, 50, "big-pkg-installer",
                             available=ok,
                             note=_("Converts the package to the Arch format and installs it. "
                                    "Prefer a native package when there is one."),
                             unavailable_reason="" if ok else _("big-pkg-installer is not installed."),
                             command=["big-pkg-installer-gui", path]))
        elif fmt == "arch-package":
            ok = bool(tools.pamac_installer)
            opts.append(make(OptionKind.INSTALL_PACKAGE_FILE, Relation.ORIGINAL, 45, "Pamac",
                             available=ok,
                             note=_("A package file from outside the repositories: it will not "
                                    "receive updates automatically."),
                             unavailable_reason="" if ok else _("Pamac is not installed."),
                             command=["pamac-installer", path]))
        elif fmt == "flatpakref":
            ok = self.system.flatpak.available()
            opts.append(make(OptionKind.INSTALL_FLATPAKREF, Relation.ORIGINAL, 15, "Flatpak",
                             title=report.metadata.get("flatpakref.Title") or report.metadata.get("flatpakref.Name", title),
                             available=ok,
                             unavailable_reason="" if ok else _("Flatpak is not installed on this system."),
                             command=["flatpak", "install", "--system", "-y", "--from", path]))
        elif fmt == "flatpak":
            ok = self.system.flatpak.available()
            opts.append(make(OptionKind.INSTALL_FLATPAKREF, Relation.ORIGINAL, 25, "Flatpak",
                             available=ok, experimental=True,
                             note=_("A Flatpak bundle does not come from a repository and will not "
                                    "be updated."),
                             unavailable_reason="" if ok else _("Flatpak is not installed on this system."),
                             command=["flatpak", "install", "--system", "-y", "--bundle", path]))

        if report.platform == Platform.WINDOWS and fmt in WINDOWS_FORMATS and report.format != "dos":
            if report.metadata.get("pe.type") == "dll":
                return opts
            if report.declared_extension == ".ps1":
                return opts
            wine_note = _("Wine runs Windows programs, but it is not a security sandbox: the "
                          "program can read and change your personal files.")
            if entry is not None and entry.get("windows", {}).get("note"):
                wine_note = pick(entry["windows"]["note"]) + " " + wine_note
            if fmt == "msi":
                cmd = ["wine", "msiexec", "/i", path]
            elif fmt == "windows-script":
                cmd = ["wine", "cmd", "/c", path]
            else:
                cmd = ["wine", path]
            ok = bool(tools.wine)
            opts.append(make(OptionKind.RUN_WINE, Relation.COMPATIBILITY, 200, "Wine",
                             title=_("Run the Windows file with Wine"), available=ok,
                             note=wine_note,
                             unavailable_reason="" if ok else _("Wine is not installed."),
                             experimental=entry is not None and entry.get("windows", {}).get("wine") in ("unsupported", "partial"),
                             command=cmd))
            if not ok:
                try:
                    wine_pkg = self.system.repos.get("wine")
                except ProviderUnavailable:
                    wine_pkg = None
                if wine_pkg and not wine_pkg.installed:
                    opts.append(Option(kind=OptionKind.INSTALL_REPO, relation=Relation.COMPATIBILITY, app_id="",
                                       title="Wine", target="wine", icon="wine",
                                       source_label=_("BigLinux repositories ({repo})").format(repo=wine_pkg.repo),
                                       note=_("Needed only if you want to run the Windows file itself."),
                                       rank=205, command=["pamac-installer", "wine"]))
            try:
                bottles = self.system.flatpak.installed("com.usebottles.bottles")
            except ProviderUnavailable:
                bottles = False
            if bottles:
                opts.append(make(OptionKind.RUN_BOTTLES, Relation.COMPATIBILITY, 210, "Bottles",
                                 title=_("Open with Bottles"),
                                 note=_("Bottles keeps each Windows program in its own Wine prefix."),
                                 command=["flatpak", "run", "com.usebottles.bottles", path]))

        if fmt in NATIVE_RUNNABLE:
            opts.append(make(OptionKind.RUN_NATIVE, Relation.ORIGINAL, 300, "",
                             title=_("Run this file"), command=[path]))
        elif fmt == "jar" and report.metadata.get("jar.runnable") == "yes":
            ok = bool(tools.java)
            opts.append(make(OptionKind.RUN_JAVA, Relation.ORIGINAL, 300, "Java",
                             title=_("Run with Java"), available=ok,
                             unavailable_reason="" if ok else _("No Java runtime is installed (package jre-openjdk)."),
                             command=["java", "-jar", path]))
        return opts

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _dedupe(options: list[Option]) -> list[Option]:
        seen, out = set(), []
        for opt in options:
            key = (opt.kind, opt.target)
            if key in seen:
                continue
            seen.add(key)
            out.append(opt)
        return out

    @staticmethod
    def _recommend(options: list[Option]) -> Option | None:
        # The same program already installed wins, even without a launcher (CLI tools).
        for opt in options:
            if opt.kind == OptionKind.OPEN_INSTALLED and opt.relation == Relation.SAME:
                return opt
        for opt in options:
            if not opt.available or opt.experimental:
                continue
            # The file itself is recommended only when it is a package to install;
            # it comes after the native options because of its rank.
            if opt.relation in (Relation.COMPATIBILITY, Relation.ORIGINAL) and opt.kind not in (
                    OptionKind.INSTALL_FLATPAKREF, OptionKind.INSTALL_PACKAGE_FILE, OptionKind.CONVERT_PACKAGE):
                continue
            if opt.kind == OptionKind.OPEN_WEBSITE and opt.relation != Relation.SAME:
                continue
            return opt
        return None


def _icon_for(entry: dict) -> str:
    linux = entry.get("linux", {})
    if linux.get("flatpak"):
        return linux["flatpak"][0]
    if linux.get("desktop"):
        return linux["desktop"][0][:-8]
    if linux.get("packages"):
        return linux["packages"][0]
    return ""
