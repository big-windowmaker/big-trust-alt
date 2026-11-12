"""Command line: big-trust-alt [--analyze FILE | --search TEXT | …] [--json]."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .core.messages import (PROVIDER_NAMES, error_text, finding_text, format_text,
                            level_text, relation_text)
from .i18n import _


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="big-trust-alt",
        description=_("Identify downloaded programs and find the best way to use them on Linux."),
    )
    p.add_argument("files", nargs="*", metavar="FILE", help=_("files to open in the window"))
    p.add_argument("--analyze", metavar="FILE", help=_("analyze a file and print the result"))
    p.add_argument("--search", metavar="TEXT", help=_("search the catalog for a program"))
    p.add_argument("--json", action="store_true", help=_("machine-readable output"))
    p.add_argument("--offline", action="store_true", help=_("do not query the AUR over the network"))
    p.add_argument("--associations", action="store_true", help=_("show the file associations"))
    p.add_argument("--associate", action="store_true",
                   help=_("make Big Trust Alt the default for downloaded programs and packages (previous choices are saved)"))
    p.add_argument("--dissociate", action="store_true", help=_("restore the previous file associations"))
    p.add_argument("--diagnostics", action="store_true", help=_("print a diagnostics report without personal data"))
    p.add_argument("--version", action="version", version=f"big-trust-alt {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.analyze:
        return _analyze(args.analyze, args.json, args.offline)
    if args.search:
        return _search(args.search, args.json, args.offline)
    if args.associations or args.associate or args.dissociate:
        from .integrations import mime
        if args.associate:
            changed = mime.associate()
            print(_("Associated: {n} file types.").format(n=len(changed)))
        elif args.dissociate:
            restored = mime.dissociate()
            print(_("Restored: {n} file types.").format(n=len(restored)))
        for mime_type, current, ours in mime.status():
            mark = "*" if ours else " "
            print(f"{mark} {mime_type:48} {current or '-'}")
        return 0
    if args.diagnostics:
        from .core.diagnostics import report
        print(report())
        return 0
    from .ui.app import run
    return run(args.files)


def _resolver(offline: bool):
    from .database.catalog import load
    from .resolvers.resolver import Preferences, Resolver
    from .core.settings import load_settings
    settings = load_settings()
    prefs = Preferences(prefer_flatpak=settings.get("prefer_flatpak", False),
                        show_aur=settings.get("show_aur", True),
                        query_aur=not offline)
    return Resolver(load(), prefs=prefs)


def _analyze(path: str, as_json: bool, offline: bool) -> int:
    from .detectors import analyze_file
    report = analyze_file(path)
    analysis = _resolver(offline).analyze(report)
    if as_json:
        json.dump(analysis.to_dict(), sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 2 if report.error else 0
    if report.error:
        print(f"{report.name}: {error_text(report.error)}", file=sys.stderr)
        return 2
    print(f"{report.name}")
    print(f"  {_('Type')}: {format_text(report)}"
          + (f" · {report.architecture}" if report.architecture else ""))
    if report.identity:
        print(f"  SHA-256: {report.identity.sha256}")
    if report.origin_url:
        print(f"  {_('Downloaded from')}: {report.origin_url}")
    print(f"  {_('Identification')}: {level_text(analysis.level)}"
          + (f" — {analysis.candidates[0].name}" if analysis.candidates and analysis.entry_id else ""))
    if analysis.level.value == "ambiguous":
        for c in analysis.candidates[:3]:
            print(f"    ? {c.name} ({c.score})")
    for f in report.findings:
        print(f"  [{f.severity}] {finding_text(f)}")
    if analysis.message:
        print(f"  {analysis.message}")
    if analysis.recommended:
        r = analysis.recommended
        print(f"  {_('Recommended')}: {r.title} — {r.source_label}")
    for o in analysis.options:
        state = "" if o.available else f"  ({o.unavailable_reason})"
        print(f"   - {relation_text(o.relation)}: {o.title} · {o.source_label}{state}")
    if analysis.providers_offline:
        names = ", ".join(PROVIDER_NAMES.get(p, p) for p in analysis.providers_offline)
        print("  " + _("Not consulted (offline or unavailable): {names}").format(names=names))
    return 0


def _search(text: str, as_json: bool, offline: bool) -> int:
    resolver = _resolver(offline)
    results = []
    for entry in resolver.search(text)[:10]:
        options = resolver.entry_analysis(entry["id"])
        results.append({"id": entry["id"], "name": entry["name"], "category": entry["category"],
                        "options": [o.to_dict() for o in options]})
    if as_json:
        json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    if not results:
        print(_("Nothing found for “{text}”.").format(text=text))
        return 1
    for item in results:
        print(item["name"])
        for o in item["options"]:
            if o["available"]:
                print(f"   - {relation_text(o['relation'])}: {o['title']} · {o['source_label']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
