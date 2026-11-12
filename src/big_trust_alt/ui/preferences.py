"""Preferences: source priority, AUR, history and file associations."""

from __future__ import annotations

from gi.repository import Adw

from ..core.settings import load_settings, save_settings
from ..i18n import _
from ..integrations import mime


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, win) -> None:
        super().__init__(title=_("Preferences"))
        self.win = win
        self.settings = load_settings()
        page = Adw.PreferencesPage(title=_("General"), icon_name="preferences-system-symbolic")
        self.add(page)

        sources = Adw.PreferencesGroup(title=_("Sources"),
                                       description=_("Safety checks stay the same whatever you choose."))
        self.flatpak = Adw.SwitchRow(title=_("Prefer Flatpak"),
                                     subtitle=_("Recommend Flathub before the system repositories"),
                                     active=self.settings["prefer_flatpak"])
        self.aur = Adw.SwitchRow(title=_("Show AUR packages"),
                                 subtitle=_("Community packages, built on your computer"),
                                 active=self.settings["show_aur"])
        sources.add(self.flatpak)
        sources.add(self.aur)
        page.add(sources)

        privacy = Adw.PreferencesGroup(title=_("Privacy"))
        self.keep = Adw.SwitchRow(title=_("Keep a history"),
                                  subtitle=_("File names, hashes and choices; stored only on this computer"),
                                  active=self.settings["keep_history"])
        privacy.add(self.keep)
        page.add(privacy)

        assoc = Adw.PreferencesGroup(
            title=_("File associations"),
            description=_("Opening a Windows program in the file manager shows Big Trust Alt. Your "
                          "previous choices are saved and come back when you turn this off."))
        self.assoc = Adw.SwitchRow(title=_("Open Windows programs with Big Trust Alt"),
                                   active=any(ours for _t, _c, ours in mime.status()))
        assoc.add(self.assoc)
        page.add(assoc)

        for row in (self.flatpak, self.aur, self.keep):
            row.connect("notify::active", self._save)
        self.assoc.connect("notify::active", self._assoc)

    def _save(self, *_args) -> None:
        self.settings = load_settings()
        self.settings.update(prefer_flatpak=self.flatpak.get_active(), show_aur=self.aur.get_active(),
                             keep_history=self.keep.get_active())
        save_settings(self.settings)
        self.win.app.reload_preferences()

    def _assoc(self, row, *_args) -> None:
        if row.get_active():
            changed = mime.associate()
            self.add_toast(Adw.Toast(title=_("Associated: {n} file types.").format(n=len(changed))))
        else:
            restored = mime.dissociate()
            self.add_toast(Adw.Toast(title=_("Restored: {n} file types.").format(n=len(restored))))
