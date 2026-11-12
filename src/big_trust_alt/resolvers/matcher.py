"""Decide which catalog entry (if any) a file is, and how sure we are.

Evidence and weights:
  package name (deb/rpm/arch/flatpak id) equal ........ 80
  product name from metadata equal ..................... 60
  file name matches a glob ............................. 45
  vendor from metadata equal ........................... 20 (only with other evidence)
  download origin on the vendor's site ................. 10 (only with other evidence)

  score >= 80  confirmed   |   score >= 40  probable   |   below: unknown
  Two candidates >= 40 less than 15 points apart: ambiguous (no choice made).
"""

from __future__ import annotations

import fnmatch
import re
from functools import lru_cache

from ..core.model import Candidate, FileReport, Level
from ..database.catalog import Catalog
from ..database.normalize import fold, normalize_filename
from ..security.fileinfo import host_of

CONFIRMED, PROBABLE, MARGIN = 80, 40, 15
_NOISE = {
    "setup", "installer", "install", "installation", "package", "edition", "release",
    "x64", "x86", "64", "32", "64bit", "32bit", "bit", "win", "win32", "win64", "windows",
    "amd64", "arm64", "stable", "latest", "full", "offline", "online", "web", "the",
    "database", "msi", "exe", "app", "for",
}
_COMPANY_NOISE = {"inc", "llc", "ltd", "limited", "corp", "corporation", "co", "gmbh", "ag",
                  "sa", "srl", "bv", "ab", "oy", "as", "pty", "plc", "foundation", "the"}
_URL = re.compile(r"https?://\S*|www\.\S*", re.I)
_EMAIL = re.compile(r"<[^>]*>|\S+@\S+")
_PUBLISHER_CN = re.compile(r"(?:^|,)\s*(?:CN|O)=\"?([^,\"]+)")
FORMAT_MAP = {"exe": "exe", "dos": "exe", "msi": "msi", "msix": "msix", "deb": "deb", "rpm": "rpm",
              "appimage": "appimage", "elf": "bin", "script": "sh", "makeself": "run", "jar": "jar",
              "flatpakref": "flatpakref", "flatpak": "flatpak", "arch-package": "arch-package",
              "tarball": "tarball"}


def product_key(text: str) -> str:
    text = _URL.sub(" ", text)
    words = [w for w in fold(text).split() if w not in _NOISE and not w.isdigit()]
    return " ".join(words)


def vendor_key(text: str) -> str:
    text = _EMAIL.sub(" ", text)
    m = _PUBLISHER_CN.search(text)
    if m:
        text = m.group(1)
    return " ".join(w for w in fold(text).split() if w not in _COMPANY_NOISE)


@lru_cache(maxsize=4096)
def _glob(pattern: str) -> re.Pattern:
    return re.compile(fnmatch.translate(pattern))


class Index:
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.products: dict[str, set[str]] = {}
        self.vendors: dict[str, set[str]] = {}
        self.packages: dict[str, set[str]] = {}
        self.globs: list[tuple[re.Pattern, str]] = []
        for entry in catalog.entries.values():
            eid = entry["id"]
            match = entry["match"]
            names = [*match.get("products", ()), entry["name"], *entry.get("aliases", ())]
            for name in names:
                key = product_key(name)
                if key:
                    self.products.setdefault(key, set()).add(eid)
            for vendor in [*match.get("vendors", ()), entry.get("vendor", "")]:
                key = vendor_key(vendor)
                if key:
                    self.vendors.setdefault(key, set()).add(eid)
            for pkg in [*match.get("packages", ()), *entry.get("linux", {}).get("flatpak", ())]:
                self.packages.setdefault(pkg.lower(), set()).add(eid)
            for glob in match.get("filenames", ()):
                self.globs.append((_glob(glob), eid))

    def _allowed(self, eid: str, fmt: str) -> bool:
        formats = self.catalog.entries[eid]["match"].get("formats")
        target = FORMAT_MAP.get(fmt)
        if fmt == "windows-script":
            return True if not formats else bool({"bat", "cmd", "ps1"} & set(formats))
        return not formats or target is None or target in formats

    def candidates(self, report: FileReport) -> list[Candidate]:
        scores: dict[str, int] = {}
        reasons: dict[str, list[str]] = {}

        def add(eid: str, points: int, why: str) -> None:
            if not self._allowed(eid, report.format):
                return
            if why in reasons.get(eid, ()):
                return
            scores[eid] = scores.get(eid, 0) + points
            reasons.setdefault(eid, []).append(why)

        meta = report.metadata
        for key in ("deb.Package", "rpm.Name", "pkg.pkgname", "flatpakref.Name"):
            value = meta.get(key, "").lower()
            for eid in self.packages.get(value, ()):
                add(eid, 80, "package")
        update = meta.get("appimage.update", "")
        if update.startswith("gh-releases"):
            parts = update.split("|")
            if len(parts) >= 3:
                for eid in self.products.get(product_key(parts[2]), ()):
                    add(eid, 60, "appimage-update-info")

        product_fields = ("pe.ProductName", "pe.FileDescription", "msi.Subject", "msi.Title",
                          "msix.DisplayName", "msix.Name", "jar.Implementation-Title",
                          "jar.Bundle-Name", "jar.Application-Name", "flatpakref.Title")
        for key in product_fields:
            value = meta.get(key, "")
            pkey = product_key(value) if value else ""
            for eid in self.products.get(pkey, ()):
                add(eid, 60, "product")

        name = normalize_filename(report.name)
        for rx, eid in self.globs:
            if rx.match(name):
                add(eid, 45, "filename")

        if scores:
            vendor_fields = ("pe.CompanyName", "msi.Author", "msix.Publisher",
                             "msix.PublisherDisplayName", "rpm.Vendor", "jar.Implementation-Vendor",
                             "deb.Maintainer")
            for key in vendor_fields:
                vkey = vendor_key(meta.get(key, ""))
                for eid in self.vendors.get(vkey, ()) if vkey else ():
                    if eid in scores:
                        add(eid, 20, "vendor")
            origin = host_of(report.origin_url) or host_of(report.referrer_url)
            for eid in list(scores):
                site = host_of(self.catalog.entries[eid].get("linux", {}).get("website", ""))
                if origin and site and _same_site(origin, site):
                    add(eid, 10, "origin")

        result = [Candidate(eid, self.catalog.entries[eid]["name"], score, reasons[eid])
                  for eid, score in scores.items()]
        result.sort(key=lambda c: (-c.score, c.name))
        return result[:5]


def _same_site(a: str, b: str) -> bool:
    def base(host: str) -> str:
        return ".".join(host.split(".")[-2:])
    return base(a) == base(b)


def classify(candidates: list[Candidate]) -> Level:
    if not candidates or candidates[0].score < PROBABLE:
        return Level.UNKNOWN
    if len(candidates) > 1 and candidates[1].score >= PROBABLE and \
            candidates[0].score - candidates[1].score < MARGIN:
        return Level.AMBIGUOUS
    return Level.CONFIRMED if candidates[0].score >= CONFIRMED else Level.PROBABLE
