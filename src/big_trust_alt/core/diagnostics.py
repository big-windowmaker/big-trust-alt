"""A diagnostics report that is safe to paste in a public issue."""

from __future__ import annotations

import os
import platform
import shutil

from .. import __version__


def report() -> str:
    from ..database.catalog import load
    from ..providers import System

    lines = [f"big-trust-alt {__version__}", f"python {platform.python_version()}",
             f"machine {platform.machine()}"]
    lines.append(f"session {os.environ.get('XDG_SESSION_TYPE', '?')} / "
                 f"desktop {os.environ.get('XDG_CURRENT_DESKTOP', '?')}")
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gtk
        lines.append(f"gtk {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}"
                     f" / libadwaita {Adw.get_major_version()}.{Adw.get_minor_version()}")
    except (ImportError, ValueError) as exc:
        lines.append(f"gtk unavailable: {exc}")
    try:
        catalog = load()
        lines.append(f"catalog {len(catalog)} entries; problems: {len(catalog.problems)}")
        lines += [f"  ! {p}" for p in catalog.problems]
    except Exception as exc:  # noqa: BLE001 - diagnostics must not crash
        lines.append(f"catalog error: {type(exc).__name__}: {exc}")
    tools = ["pacman", "pamac-installer", "flatpak", "wine", "big-pkg-installer-gui", "java", "steam"]
    lines.append("tools " + ", ".join(f"{t}={'yes' if shutil.which(t) else 'no'}" for t in tools))
    system = System()
    try:
        system.repos.get("pacman")
        lines.append("repos ok")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"repos unavailable: {exc}")
    home = os.path.expanduser("~")
    return "\n".join(lines).replace(home, "~")
