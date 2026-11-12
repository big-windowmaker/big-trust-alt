"""Gtk.Application: one window per opened file, shared catalog and providers."""

from __future__ import annotations

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .. import __version__  # noqa: E402
from ..i18n import _, bind_gtk  # noqa: E402

APP_ID = "io.github.big_windowmaker.BigTrustAlt"
_DEV_ICONS = Path(__file__).resolve().parents[3] / "data" / "icons"


class Application(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.HANDLES_OPEN | Gio.ApplicationFlags.NON_UNIQUE)
        GLib.set_application_name("Big Trust Alt")
        self._resolver = None
        self._system = None

    # Lazy: the catalog loads once, off the startup path of the first window.
    def resolver(self):
        if self._resolver is None:
            from ..core.settings import load_settings
            from ..database.catalog import load
            from ..providers import System
            from ..resolvers.resolver import Preferences, Resolver
            s = load_settings()
            self._system = System()
            self._resolver = Resolver(load(), self._system,
                                      Preferences(prefer_flatpak=s["prefer_flatpak"], show_aur=s["show_aur"]))
        return self._resolver

    def reload_preferences(self) -> None:
        if self._resolver is not None:
            from ..core.settings import load_settings
            s = load_settings()
            self._resolver.prefs.prefer_flatpak = s["prefer_flatpak"]
            self._resolver.prefs.show_aur = s["show_aur"]

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        bind_gtk()
        display = Gdk.Display.get_default()
        if display and _DEV_ICONS.is_dir():
            Gtk.IconTheme.get_for_display(display).add_search_path(str(_DEV_ICONS))
        css = Gtk.CssProvider()
        css.load_from_string(CSS)
        if display:
            Gtk.StyleContext.add_provider_for_display(display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        for name, accels, cb in (
            ("open", ["<Control>o"], lambda *_: self._active().choose_file()),
            ("search", ["<Control>f"], lambda *_: self._active().show_search()),
            ("history", ["<Control>h"], lambda *_: self._active().show_history()),
            ("preferences", ["<Control>comma"], lambda *_: self._active().show_preferences()),
            ("about", [], lambda *_: self._about()),
            ("close", ["<Control>w"], lambda *_: self._active().close()),
            ("quit", ["<Control>q"], lambda *_: self.quit()),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)

    def _active(self):
        from .window import Window
        win = self.get_active_window()
        return win if isinstance(win, Window) else self._new_window()

    def _new_window(self):
        from .window import Window
        win = Window(self)
        win.present()
        return win

    def do_activate(self) -> None:
        self._new_window()

    def do_open(self, files, n_files, hint) -> None:
        for gfile in files:
            win = self._new_window()
            if gfile.get_path():
                win.analyze(gfile.get_path())

    def _about(self) -> None:
        about = Adw.AboutDialog(
            application_name="Big Trust Alt",
            application_icon=APP_ID,
            version=__version__,
            developer_name="Big WindowMaker",
            comments=_("Identifies programs downloaded from the internet and shows the best way "
                       "to use them on Linux: native packages first, without taking away your choice."),
            website="https://github.com/big-windowmaker/big-trust-alt",
            issue_url="https://github.com/big-windowmaker/big-trust-alt/issues",
            license_type=Gtk.License.GPL_3_0,
            developers=["Rafael Ruscher <rruscher@gmail.com>",
                        "Barnabé Di Kartola <barnabedikartola@gmail.com>"],
            copyright="© 2026 Big WindowMaker",
        )
        about.add_acknowledgement_section(_("Based on ideas and data from"), [
            "Zorin Exec Guard https://github.com/ruscher/zorin-exec-guard",
            "Zorin Exec Guard App DB https://github.com/ruscher/zorin-exec-guard-app-db",
        ])
        about.add_acknowledgement_section(_("Works with"), [
            "big-pkg-installer https://github.com/biglinux/big-pkg-installer",
            "Pamac https://github.com/manjaro/pamac",
            "Flatpak https://flatpak.org",
        ])
        about.add_acknowledgement_section(_("Special thanks"), [
            "Bruno Gonçalves (BigLinux)", "Tales A. Mendonça (BigCommunity)",
        ])
        about.present(self.get_active_window())


CSS = """
.hero-title { font-size: 1.6em; font-weight: 800; }
.file-name { font-family: monospace; }
.recommend-card { padding: 18px; border-radius: 14px;
  background: color-mix(in srgb, var(--accent-bg-color) 10%, var(--card-bg-color));
  border: 1px solid color-mix(in srgb, var(--accent-bg-color) 45%, transparent); }
.recommend-card .eyebrow { color: color-mix(in srgb, var(--accent-color) 60%, var(--window-fg-color));
  font-weight: 700; font-size: 0.85em; letter-spacing: 0.04em; }
.option-title { font-weight: 700; font-size: 1.15em; }
.badge { border-radius: 99px; padding: 2px 10px; font-size: 0.8em; font-weight: 700; }
.badge.same, .badge.installed { background: color-mix(in srgb, var(--success-bg-color) 24%, transparent);
  color: color-mix(in srgb, var(--success-color) 55%, var(--window-fg-color)); }
.badge.alt { background: color-mix(in srgb, var(--accent-bg-color) 22%, transparent);
  color: color-mix(in srgb, var(--accent-color) 55%, var(--window-fg-color)); }
.badge.compat { background: color-mix(in srgb, var(--warning-bg-color) 28%, transparent);
  color: color-mix(in srgb, var(--warning-color) 55%, var(--window-fg-color)); }
.badge.original, .badge.neutral { background: alpha(currentColor, 0.1); }
.badge.danger { background: color-mix(in srgb, var(--error-bg-color) 24%, transparent);
  color: color-mix(in srgb, var(--error-color) 55%, var(--window-fg-color)); }
.alert-card { padding: 14px; border-radius: 12px; }
.alert-card.danger { background: color-mix(in srgb, var(--error-bg-color) 14%, var(--card-bg-color));
  border: 1px solid color-mix(in srgb, var(--error-bg-color) 50%, transparent); }
.alert-card.info { background: color-mix(in srgb, var(--accent-bg-color) 8%, var(--card-bg-color)); }
.script-view { font-family: monospace; font-size: 0.92em; padding: 10px; }
.drop-highlight { background: color-mix(in srgb, var(--accent-bg-color) 12%, transparent); }
/* Themes that replace the libadwaita stylesheet (GTK_THEME, e.g. BigWindowMaker)
   do not style dialog sheets; without this the dialogs have no background. */
floating-sheet > sheet, bottom-sheet > sheet, dialog.floating sheet {
  background-color: var(--dialog-bg-color, @theme_bg_color); color: var(--dialog-fg-color, @theme_fg_color);
  border-radius: 12px; box-shadow: 0 4px 18px rgba(0, 0, 0, 0.35), 0 0 0 1px rgba(0, 0, 0, 0.12); }
floating-sheet > dimming, bottom-sheet > dimming { background-color: rgba(0, 0, 0, 0.25); }
dialog.alert .message-area { padding: 20px 20px 12px 20px; }
dialog.alert .response-area { padding: 8px 12px 12px 12px; }
dialog.alert .response-area > button { margin: 0 4px; }
"""


def run(files: list[str]) -> int:
    app = Application()
    argv = [sys.argv[0], *files]
    return app.run(argv)
