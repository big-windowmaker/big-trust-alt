"""Main window: home, analysis result, progress, search and history pages."""

from __future__ import annotations

import os
import threading
import time

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from ..core import history
from ..core.messages import (PROVIDER_NAMES, action_text, error_text, finding_text,
                             format_text, level_text, relation_text)
from ..core.model import Analysis, Level, Option, OptionKind, Platform, Relation, Severity
from ..i18n import _, pick
from ..security.fileinfo import display_name, host_of

RELATION_CLASS = {
    Relation.SAME: "same", Relation.SUCCESSOR: "alt", Relation.ALTERNATIVE: "alt",
    Relation.WEB: "alt", Relation.LAUNCHER: "alt", Relation.COMPATIBILITY: "compat",
    Relation.ORIGINAL: "original",
}
KIND_ICON = {
    OptionKind.OPEN_INSTALLED: "media-playback-start-symbolic",
    OptionKind.INSTALL_REPO: "system-software-install-symbolic",
    OptionKind.INSTALL_FLATPAK: "system-software-install-symbolic",
    OptionKind.INSTALL_AUR: "system-software-install-symbolic",
    OptionKind.INSTALL_PACKAGE_FILE: "system-software-install-symbolic",
    OptionKind.CONVERT_PACKAGE: "package-x-generic-symbolic",
    OptionKind.INSTALL_FLATPAKREF: "system-software-install-symbolic",
    OptionKind.OPEN_WEBSITE: "web-browser-symbolic",
    OptionKind.OPEN_STEAM: "input-gaming-symbolic",
    OptionKind.RUN_WINE: "application-x-executable-symbolic",
    OptionKind.RUN_BOTTLES: "application-x-executable-symbolic",
    OptionKind.RUN_NATIVE: "application-x-executable-symbolic",
    OptionKind.RUN_JAVA: "application-x-executable-symbolic",
}
FORMAT_ICON = {"exe": "application-x-ms-dos-executable", "msi": "application-x-msi",
               "deb": "application-vnd.debian.binary-package", "rpm": "application-x-rpm",
               "appimage": "application-x-executable", "jar": "application-x-java-archive",
               "script": "text-x-script", "arch-package": "package-x-generic"}
RUN_KINDS = {OptionKind.RUN_WINE, OptionKind.RUN_BOTTLES, OptionKind.RUN_NATIVE, OptionKind.RUN_JAVA}


def _label(text: str, *classes: str, wrap: bool = True, xalign: float = 0, selectable: bool = False) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=xalign, wrap=wrap, selectable=selectable)
    label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    for css in classes:
        label.add_css_class(css)
    return label


def _badge(text: str, css: str) -> Gtk.Label:
    label = Gtk.Label(label=text)
    label.add_css_class("badge")
    label.add_css_class(css)
    label.set_valign(Gtk.Align.CENTER)
    return label


def _icon(name: str, size: int, fallback: str = "application-x-executable") -> Gtk.Image:
    display = Gdk.Display.get_default()
    theme = Gtk.IconTheme.get_for_display(display) if display else None
    chosen = name if name and theme and theme.has_icon(name) else fallback
    image = Gtk.Image.new_from_icon_name(chosen)
    image.set_pixel_size(size)
    image.set_accessible_role(Gtk.AccessibleRole.PRESENTATION)
    return image


class Window(Adw.ApplicationWindow):
    def __init__(self, app) -> None:
        super().__init__(application=app, title="Big Trust Alt")
        self.app = app
        self.set_default_size(720, 720)
        self.set_size_request(360, 420)
        self.analysis: Analysis | None = None
        self._cancel_analysis = threading.Event()

        self.toasts = Adw.ToastOverlay()
        self.nav = Adw.NavigationView()
        self.toasts.set_child(self.nav)
        self.set_content(self.toasts)
        self.nav.add(self._home_page())

        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        drop.connect("enter", lambda *_: (self.add_css_class("drop-highlight"), Gdk.DragAction.COPY)[1])
        drop.connect("leave", lambda *_: self.remove_css_class("drop-highlight"))
        self.add_controller(drop)

    # -- shared chrome --------------------------------------------------------
    def _page(self, title: str, tag: str, content: Gtk.Widget, scroll: bool = True,
              header_end: list[Gtk.Widget] | None = None) -> Adw.NavigationPage:
        header = Adw.HeaderBar()
        menu = Gio.Menu()
        section = Gio.Menu()
        section.append(_("Open file…"), "app.open")
        section.append(_("Find an alternative…"), "app.search")
        section.append(_("History"), "app.history")
        menu.append_section(None, section)
        section2 = Gio.Menu()
        section2.append(_("Preferences"), "app.preferences")
        section2.append(_("About Big Trust Alt"), "app.about")
        menu.append_section(None, section2)
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                     tooltip_text=_("Main menu"), primary=True)
        header.pack_end(menu_button)
        for widget in header_end or ():
            header.pack_end(widget)
        view = Adw.ToolbarView()
        view.add_top_bar(header)
        if scroll:
            clamp = Adw.Clamp(maximum_size=680, tightening_threshold=480, child=content)
            scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True,
                                          child=clamp)
            view.set_content(scroller)
        else:
            view.set_content(content)
        return Adw.NavigationPage(title=title, tag=tag, child=view)

    def toast(self, text: str) -> None:
        self.toasts.add_toast(Adw.Toast(title=text, timeout=4))

    # -- home -------------------------------------------------------------------
    def _home_page(self) -> Adw.NavigationPage:
        status = Adw.StatusPage(
            icon_name="io.github.big_windowmaker.BigTrustAlt",
            title=_("Open a downloaded program"),
            description=_("Drop a file here or choose one. Big Trust Alt finds out what it is and "
                          "the best way to use it on Linux. Nothing is run during the analysis."),
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, halign=Gtk.Align.CENTER)
        choose = Gtk.Button(label=_("Choose a file…"), action_name="app.open")
        choose.add_css_class("pill")
        choose.add_css_class("suggested-action")
        search = Gtk.Button(label=_("Find a Linux alternative for a program"), action_name="app.search")
        search.add_css_class("pill")
        box.append(choose)
        box.append(search)
        status.set_child(box)
        return self._page("Big Trust Alt", "home", status, scroll=False)

    def choose_file(self) -> None:
        dialog = Gtk.FileDialog(title=_("Choose a downloaded file"), modal=True)
        downloads = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
        if downloads and os.path.isdir(downloads):
            dialog.set_initial_folder(Gio.File.new_for_path(downloads))

        def done(dlg, result):
            try:
                gfile = dlg.open_finish(result)
            except GLib.Error:
                return
            if gfile and gfile.get_path():
                self.analyze(gfile.get_path())
        dialog.open(self, None, done)

    def _on_drop(self, _target, value, _x, _y) -> bool:
        self.remove_css_class("drop-highlight")
        files = value.get_files() if value else []
        paths = [f.get_path() for f in files if f.get_path()]
        if not paths:
            self.toast(_("Only local files can be analyzed."))
            return False
        self.analyze(paths[0])
        for extra in paths[1:4]:
            win = Window(self.app)
            win.present()
            win.analyze(extra)
        return True

    # -- analysis -------------------------------------------------------------
    def analyze(self, path: str, chosen: str | None = None) -> None:
        self._cancel_analysis.clear()
        spinner = Adw.Spinner(width_request=48, height_request=48)
        status = Adw.StatusPage(title=_("Analyzing…"), description=display_name(os.path.basename(path)),
                                child=spinner)
        cancel = Gtk.Button(label=_("Cancel"), halign=Gtk.Align.CENTER)
        cancel.add_css_class("pill")
        cancel.connect("clicked", lambda *_: (self._cancel_analysis.set(), self.nav.pop_to_tag("home")))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        box.append(status)
        box.append(cancel)
        page = self._page(_("Analyzing"), "analyzing", box, scroll=False)
        self.nav.pop_to_tag("home")
        self.nav.push(page)
        started = time.monotonic()

        def work():
            from ..detectors import analyze_file
            report = analyze_file(path, cancel=self._cancel_analysis.is_set)
            result = self.app.resolver().analyze(report, chosen=chosen)
            GLib.idle_add(self._show_result, result, time.monotonic() - started)

        threading.Thread(target=work, daemon=True, name="analyze").start()

    def _show_result(self, analysis: Analysis, elapsed: float) -> bool:
        if self._cancel_analysis.is_set():
            return False
        self.analysis = analysis
        page = ResultPage(self, analysis).page
        if self.nav.get_visible_page() and self.nav.get_visible_page().get_tag() == "analyzing":
            self.nav.pop_to_tag("home")
        self.nav.push(page)
        report = analysis.report
        if not report.error:
            history.record(report.name, report.identity.sha256 if report.identity else "",
                           report.format, analysis.entry_id, "analyze", str(analysis.level))
        return False

    # -- actions ------------------------------------------------------------------
    def activate_option(self, option: Option) -> None:
        from ..installers import runner
        report = self.analysis.report if self.analysis else None
        kind = option.kind
        if kind == OptionKind.OPEN_INSTALLED:
            if option.command[:2] == ["flatpak", "run"]:
                runner.launch_detached(option.command)
                ok = True
            else:
                try:
                    info = Gio.DesktopAppInfo.new(option.target)
                    ok = bool(info and info.launch([], None))
                except (GLib.Error, TypeError):
                    ok = False
            self.toast(_("Opening {name}…").format(name=option.title) if ok else _("Could not open the program."))
            self._record(option, "launched" if ok else "failed")
            return
        if kind in (OptionKind.OPEN_WEBSITE, OptionKind.OPEN_STEAM):
            uri = option.target if kind == OptionKind.OPEN_WEBSITE else f"steam://store/{option.target}"
            Gtk.UriLauncher.new(uri).launch(self, None, None)
            self._record(option, "launched")
            return
        if kind == OptionKind.CONVERT_PACKAGE:
            runner.launch_detached(["big-pkg-installer-gui", option.target])
            self.toast(_("Opened in big-pkg-installer."))
            self._record(option, "launched")
            return
        if kind in RUN_KINDS:
            RunDialog(self, option, report).present(self)
            return
        ProgressPage(self, option).start()

    def _record(self, option: Option, result: str) -> None:
        report = self.analysis.report if self.analysis else None
        history.record(report.name if report else option.title,
                       report.identity.sha256 if report and report.identity else "",
                       report.format if report else "", option.app_id, str(option.kind), result)

    # -- other pages --------------------------------------------------------------
    def show_search(self) -> None:
        self.nav.push(SearchPage(self).page)

    def show_history(self) -> None:
        self.nav.push(HistoryPage(self).page)

    def show_preferences(self) -> None:
        from .preferences import PreferencesDialog
        PreferencesDialog(self).present(self)


# ---------------------------------------------------------------------------------
class ResultPage:
    def __init__(self, win: Window, analysis: Analysis) -> None:
        self.win = win
        self.analysis = analysis
        report = analysis.report
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                      margin_top=24, margin_bottom=24, margin_start=16, margin_end=16)
        self.box = box
        if report.error:
            box.append(Adw.StatusPage(icon_name="dialog-error-symbolic", title=_("Could not analyze"),
                                      description=error_text(report.error)))
            self.page = win._page(_("Result"), "result", box)
            return
        catalog = win.app.resolver().catalog
        entry = catalog.get(analysis.entry_id) if analysis.entry_id else None
        self._hero(report, entry)
        self._dangers(report)
        if analysis.message:
            card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            card.add_css_class("alert-card")
            card.add_css_class("info")
            card.append(_icon("dialog-information-symbolic", 24))
            card.append(_label(analysis.message))
            box.append(card)
        if analysis.level == Level.AMBIGUOUS:
            self._ambiguous()
        self._recommended()
        self._options()
        self._original()
        self._details(report)
        self._footer()
        self.page = win._page(entry["name"] if entry else _("Result"), "result", box)

    # hero ---------------------------------------------------------------------
    def _hero(self, report, entry) -> None:
        a = self.analysis
        icon_name = ""
        if entry:
            from ..resolvers.resolver import _icon_for
            icon_name = _icon_for(entry)
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER)
        hero.append(_icon(icon_name, 96, FORMAT_ICON.get(report.format, "application-x-executable")))
        file_label = _label(display_name(report.name), "dim-label", "file-name", xalign=0.5)
        file_label.set_tooltip_text(report.path)
        hero.append(file_label)
        if entry:
            if report.platform == Platform.WINDOWS:
                headline = _("We found a better way to use this program on Linux.")
            else:
                headline = _("We found the best way to install this program.")
            hero.append(_label(headline, "hero-title", xalign=0.5))
            what = _("{kind} identified as {name}").format(
                kind=format_text(report), name=entry["name"])
            hero.append(_label(what, xalign=0.5))
        else:
            title = _("Choose which program this is") if a.level == Level.AMBIGUOUS \
                else _("We could not identify this program")
            hero.append(_label(title, "hero-title", xalign=0.5))
            hero.append(_label(format_text(report), xalign=0.5))
        badges = Adw.WrapBox(child_spacing=6, line_spacing=6, halign=Gtk.Align.CENTER, justify=Adw.JustifyMode.NONE)
        css = {"confirmed": "same", "probable": "alt", "ambiguous": "compat", "unknown": "neutral"}[a.level]
        badges.append(_badge(level_text(a.level), css))
        platform = {Platform.WINDOWS: _("Made for Windows"), Platform.LINUX: _("Made for Linux"),
                    Platform.JAVA: _("Java")}.get(report.platform)
        if platform:
            badges.append(_badge(platform, "neutral"))
        if report.architecture:
            badges.append(_badge(report.architecture, "neutral"))
        hero.append(badges)
        if a.level != Level.CONFIRMED and entry:
            hero.append(_label(_("Identified by name and file details; it is not a guarantee of origin."),
                               "dim-label", "caption", xalign=0.5))
        self.box.append(hero)

    def _dangers(self, report) -> None:
        dangers = [f for f in report.findings if f.severity == Severity.DANGER]
        if not dangers:
            return
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("alert-card")
        card.add_css_class("danger")
        card.append(_label(_("Be careful with this file"), "heading"))
        for f in dangers:
            card.append(_label("• " + finding_text(f)))
        self.box.append(card)

    def _ambiguous(self) -> None:
        group = Adw.PreferencesGroup(title=_("Which of these is it?"),
                                     description=_("The file matches more than one program. Choose one; "
                                                   "nothing is installed yet."))
        for cand in self.analysis.candidates[:4]:
            row = Adw.ActionRow(title=cand.name, activatable=True)
            row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            row.connect("activated", lambda _r, c=cand: self.win.analyze(self.analysis.report.path, c.entry_id))
            group.add(row)
        self.box.append(group)

    # recommended ------------------------------------------------------------------
    def _recommended(self) -> None:
        opt = self.analysis.recommended
        if not opt:
            return
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("recommend-card")
        card.append(_label(_("RECOMMENDED FOR BIGLINUX"), "eyebrow"))
        row = Gtk.Box(spacing=14)
        row.append(_icon(opt.icon, 48))
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True, valign=Gtk.Align.CENTER)
        text.append(_label(opt.title, "option-title"))
        badges = Adw.WrapBox(child_spacing=6, line_spacing=4)
        badges.append(_badge(relation_text(opt.relation), RELATION_CLASS[opt.relation]))
        badges.append(_badge(opt.source_label, "neutral"))
        text.append(badges)
        row.append(text)
        card.append(row)
        card.append(_label(self._why(opt), "dim-label"))
        if opt.note:
            card.append(_label(opt.note, "caption"))
        if not opt.available:
            card.append(_label(opt.unavailable_reason, "caption"))
            self.box.append(card)
            return
        button = Gtk.Button(label=self._primary_label(opt), halign=Gtk.Align.END)
        button.add_css_class("suggested-action")
        button.add_css_class("pill")
        button.connect("clicked", lambda *_: self.win.activate_option(opt))
        card.append(button)
        self.box.append(card)
        GLib.idle_add(lambda: button.grab_focus() and False)

    @staticmethod
    def _primary_label(opt: Option) -> str:
        if opt.kind == OptionKind.OPEN_INSTALLED:
            return _("Open installed program")
        if opt.kind in (OptionKind.INSTALL_REPO, OptionKind.INSTALL_FLATPAK, OptionKind.INSTALL_AUR):
            return _("Install Linux version") if opt.relation == Relation.SAME else _("Install {name}").format(name=opt.title)
        return action_text(opt.kind)

    @staticmethod
    def _why(opt: Option) -> str:
        return {
            OptionKind.OPEN_INSTALLED: _("It is already installed: nothing to download."),
            OptionKind.INSTALL_REPO: _("Comes from the system repositories: tested with BigLinux and "
                                       "updated with the rest of the system."),
            OptionKind.INSTALL_FLATPAK: _("Flatpak from Flathub: runs isolated from the system and "
                                          "updates by itself."),
            OptionKind.INSTALL_AUR: _("Built from the AUR, the community repository."),
            OptionKind.OPEN_WEBSITE: _("The developer offers a Linux version on the official website."),
            OptionKind.OPEN_STEAM: _("Available on Steam, which runs it on Linux."),
            OptionKind.INSTALL_FLATPAKREF: _("This file points to a Flatpak app."),
            OptionKind.INSTALL_PACKAGE_FILE: _("An Arch package can be installed directly."),
        }.get(opt.kind, "")

    # other options -----------------------------------------------------------------
    def _options(self) -> None:
        rest = [o for o in self.analysis.options
                if o is not self.analysis.recommended and o.kind not in RUN_KINDS
                and o.relation != Relation.COMPATIBILITY]
        if not rest:
            return
        group = Adw.PreferencesGroup(title=_("Other options") if self.analysis.recommended else _("Options"))
        for opt in rest:
            group.add(self._row(opt))
        self.box.append(group)
        if self.analysis.providers_offline:
            names = ", ".join(PROVIDER_NAMES.get(p, p) for p in self.analysis.providers_offline)
            self.box.append(_label(_("Not consulted (offline or unavailable): {names}").format(names=names),
                                   "dim-label", "caption"))

    def _row(self, opt: Option) -> Adw.ActionRow:
        subtitle = " · ".join(x for x in (relation_text(opt.relation), opt.source_label) if x)
        if not opt.available:
            subtitle += "\n" + opt.unavailable_reason
        elif opt.note:
            subtitle += "\n" + opt.note
        row = Adw.ActionRow(title=GLib.markup_escape_text(opt.title), subtitle=GLib.markup_escape_text(subtitle),
                            subtitle_lines=4)
        row.add_prefix(_icon(opt.icon, 32, KIND_ICON[opt.kind]))
        if opt.experimental:
            row.add_suffix(_badge(_("Experimental"), "compat"))
        button = Gtk.Button(label=action_text(opt.kind), valign=Gtk.Align.CENTER, sensitive=opt.available)
        button.connect("clicked", lambda *_: self.win.activate_option(opt))
        button.update_property([Gtk.AccessibleProperty.LABEL], [f"{action_text(opt.kind)} {opt.title}"])
        row.add_suffix(button)
        row.set_activatable_widget(button)
        return row

    def _original(self) -> None:
        runs = [o for o in self.analysis.options if o.kind in RUN_KINDS or o.relation == Relation.COMPATIBILITY]
        report = self.analysis.report
        if not runs and not report.preview:
            return
        group = Adw.PreferencesGroup(title=_("Original file"),
                                     description=_("Run it only if you trust where it came from."))
        if report.preview:
            row = Adw.ActionRow(title=_("View the content"), activatable=True,
                                subtitle=_("Read the script before deciding."))
            row.add_prefix(_icon("text-x-script-symbolic", 24))
            row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            row.connect("activated", lambda *_: self.win.nav.push(ScriptPage(self.win, report).page))
            group.add(row)
        for opt in runs:
            group.add(self._row(opt))
        self.box.append(group)

    # details ---------------------------------------------------------------------------
    def _details(self, report) -> None:
        group = Adw.PreferencesGroup(title=_("Details"))
        expander = Adw.ExpanderRow(title=_("Technical details"),
                                   subtitle=_("Type, hash, origin and file information"))
        def add(title, value, copy=False):
            if not value:
                return
            row = Adw.ActionRow(title=title, subtitle=GLib.markup_escape_text(str(value)),
                                subtitle_selectable=True)
            row.add_css_class("property")
            if copy:
                b = Gtk.Button(icon_name="edit-copy-symbolic", valign=Gtk.Align.CENTER,
                               tooltip_text=_("Copy"))
                b.add_css_class("flat")
                b.connect("clicked", lambda *_: (self.win.get_clipboard().set(str(value)),
                                                 self.win.toast(_("Copied"))))
                row.add_suffix(b)
            expander.add_row(row)
        add(_("Type"), format_text(report))
        add(_("Size"), GLib.format_size(report.size))
        if report.identity:
            add("SHA-256", report.identity.sha256, copy=True)
        if report.origin_url:
            add(_("Downloaded from"), report.origin_url, copy=True)
        add(_("Location"), report.path)
        add(_("Symbolic link to"), report.symlink_target)
        add(_("Executable permission"), _("Yes") if report.executable_bit else _("No"))
        for key, value in sorted(report.metadata.items()):
            add(key, value)
        for f in report.findings:
            if f.severity != Severity.DANGER:
                add(_("Note"), finding_text(f))
        for c in self.analysis.candidates[:3]:
            add(_("Candidate"), f"{c.name} · {c.score} · {', '.join(c.reasons)}")
        for opt in self.analysis.options:
            if opt.command:
                add(_("Command for “{title}”").format(title=opt.title), " ".join(opt.command))
        group.add(expander)
        self.box.append(group)

    def _footer(self) -> None:
        box = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        other = Gtk.Button(label=_("Analyze another file"), action_name="app.open")
        other.add_css_class("pill")
        report = Gtk.Button(label=_("Report a wrong match"))
        report.add_css_class("pill")
        report.add_css_class("flat")
        report.connect("clicked", self._report_wrong)
        box.append(other)
        box.append(report)
        self.box.append(box)

    def _report_wrong(self, *_args) -> None:
        a = self.analysis
        r = a.report
        meta = {k: v for k, v in r.metadata.items() if not k.endswith(("Copyright",))}
        text = "\n".join([
            "### Big Trust Alt — wrong or missing match",
            f"- file name: `{os.path.basename(r.name)}`",
            f"- format: {r.format} · {r.architecture}",
            f"- sha256: {r.identity.sha256 if r.identity else '?'}",
            f"- origin host: {host_of(r.origin_url) or '-'}",
            f"- result: {a.level} {a.entry_id or ''}",
            f"- candidates: {', '.join(f'{c.entry_id}={c.score}' for c in a.candidates) or '-'}",
            "- metadata:",
            *[f"  - {k}: {v}" for k, v in sorted(meta.items())],
            "",
            "Expected program: ",
        ])
        dialog = Adw.AlertDialog(
            heading=_("Report a wrong match"),
            body=_("This report was copied to the clipboard. It has no folder names or personal "
                   "data; check it before posting. Nothing is sent automatically."),
        )
        view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        view.get_buffer().set_text(text)
        view.add_css_class("script-view")
        scroller = Gtk.ScrolledWindow(child=view, min_content_height=160, max_content_height=260,
                                      propagate_natural_height=True)
        dialog.set_extra_child(scroller)
        dialog.add_response("close", _("Close"))
        dialog.add_response("issue", _("Open the issue page"))
        dialog.set_default_response("close")
        self.win.get_clipboard().set(text)

        def on_response(_d, response):
            if response == "issue":
                Gtk.UriLauncher.new("https://github.com/big-windowmaker/big-trust-alt/issues/new").launch(
                    self.win, None, None)
        dialog.connect("response", on_response)
        dialog.present(self.win)


# ---------------------------------------------------------------------------------------
class RunDialog(Adw.AlertDialog):
    """Explicit confirmation before running the original file."""

    def __init__(self, win: Window, option: Option, report) -> None:
        windows = option.kind in (OptionKind.RUN_WINE, OptionKind.RUN_BOTTLES)
        body = [_("Programs run with your permissions: they can read and change your files.")]
        if windows:
            body.append(_("Wine is not a sandbox. Prefer the Linux options when there is one."))
        notes = [f for f in report.findings if f.severity != Severity.INFO] if report else []
        if notes:
            body.append(_("Notes about this file:") + "\n" + "\n".join("• " + finding_text(f) for f in notes))
        super().__init__(heading=_("Run “{name}”?").format(name=display_name(report.name if report else option.title)),
                         body="\n\n".join(b for b in body if b.strip()))
        self.win, self.option, self.report = win, option, report
        extra = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.make_exec = None
        if option.kind == OptionKind.RUN_NATIVE and report and not report.executable_bit:
            self.make_exec = Gtk.CheckButton(label=_("Allow this file to run (mark as executable)"))
            extra.append(self.make_exec)
        self.terminal = Gtk.CheckButton(label=_("Open in a terminal to see its messages"))
        self.terminal.set_active(bool(report and report.format in ("script", "makeself")))
        if option.kind != OptionKind.RUN_BOTTLES:
            extra.append(self.terminal)
        if report and report.identity:
            extra.append(_label("SHA-256: " + report.identity.sha256, "caption", "dim-label", selectable=True))
        self.set_extra_child(extra)
        self.add_response("cancel", _("Cancel"))
        self.add_response("run", _("Run"))
        self.set_response_appearance("run", Adw.ResponseAppearance.DESTRUCTIVE)
        self.set_default_response("cancel")
        self.set_close_response("cancel")
        if self.make_exec:
            self.set_response_enabled("run", False)
            self.make_exec.connect("toggled", lambda b: self.set_response_enabled("run", b.get_active()))
        self.connect("response", self._on_response)

    def _on_response(self, _d, response) -> None:
        if response != "run":
            return
        from ..installers.runner import Outcome, run_original
        result = run_original(self.option, self.report.identity if self.report else None,
                              bool(self.make_exec and self.make_exec.get_active()),
                              self.terminal.get_active())
        self.win._record(self.option, str(result.outcome))
        if result.outcome == Outcome.LAUNCHED:
            self.win.toast(_("Started."))
        else:
            self.win.toast(result.message or _("Could not run the file."))


# ---------------------------------------------------------------------------------------
class ProgressPage:
    def __init__(self, win: Window, option: Option) -> None:
        from ..installers.runner import Job
        self.win, self.option = win, option
        self.job = Job(option, on_line=lambda line: GLib.idle_add(self._line, line))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                      margin_top=32, margin_bottom=24, margin_start=16, margin_end=16)
        self.icon = _icon(option.icon, 80, KIND_ICON[option.kind])
        box.append(self.icon)
        self.title = _label(_("Installing {name}").format(name=option.title), "title-2", xalign=0.5)
        box.append(self.title)
        self.status = _label(_("Starting…"), "dim-label", xalign=0.5)
        box.append(self.status)
        self.bar = Gtk.ProgressBar(show_text=False)
        box.append(self.bar)
        self.log = Gtk.TextView(editable=False, monospace=True, cursor_visible=False,
                                wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.log.add_css_class("script-view")
        expander = Gtk.Expander(label=_("Show messages"),
                                child=Gtk.ScrolledWindow(child=self.log, min_content_height=160))
        box.append(expander)
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        self.cancel = Gtk.Button(label=_("Cancel"), sensitive=self.job.cancellable)
        self.cancel.add_css_class("pill")
        self.cancel.connect("clicked", lambda *_: (self.job.cancel(), self.status.set_text(_("Cancelling…"))))
        if not self.job.cancellable:
            self.cancel.set_tooltip_text(_("Cancel in the Pamac window."))
        self.open = Gtk.Button(label=_("Open"), visible=False)
        self.open.add_css_class("pill")
        self.open.add_css_class("suggested-action")
        self.open.connect("clicked", self._open)
        buttons.append(self.cancel)
        buttons.append(self.open)
        box.append(buttons)
        self.page = win._page(_("Installation"), "progress", box)
        self.page.set_can_pop(False)
        self._pulse = 0

    def start(self) -> None:
        self.win.nav.push(self.page)
        self._pulse = GLib.timeout_add(120, self._tick)
        threading.Thread(target=self._work, daemon=True, name="install").start()

    def _tick(self) -> bool:
        self.bar.pulse()
        return True

    def _line(self, line: str) -> bool:
        buf = self.log.get_buffer()
        buf.insert(buf.get_end_iter(), line + "\n")
        self.status.set_text(line[:120])
        import re
        m = re.search(r"(\d{1,3})%", line)
        if m and self._pulse:
            GLib.source_remove(self._pulse)
            self._pulse = 0
        if m:
            self.bar.set_fraction(min(int(m.group(1)), 100) / 100)
        return False

    def _work(self) -> None:
        result = self.job.run()
        GLib.idle_add(self._done, result)

    def _done(self, result) -> bool:
        from ..installers.runner import Outcome
        if self._pulse:
            GLib.source_remove(self._pulse)
            self._pulse = 0
        self.cancel.set_visible(False)
        self.page.set_can_pop(True)
        self.win._record(self.option, str(result.outcome))
        if result.outcome == Outcome.DONE:
            self.bar.set_fraction(1)
            self.title.set_text(_("{name} is installed").format(name=self.option.title))
            self.status.set_text(_("Installed and verified."))
            self.open.set_visible(self.option.kind in (OptionKind.INSTALL_REPO, OptionKind.INSTALL_FLATPAK,
                                                       OptionKind.INSTALL_AUR))
            self.win.app.resolver().system.repos.refresh_installed()
            self.win.app.resolver().system.flatpak.refresh()
        else:
            self.bar.set_fraction(0)
            self.title.set_text({Outcome.CANCELLED: _("Installation cancelled")}.get(
                result.outcome, _("Installation not completed")))
            self.status.set_text(result.message or "")
        return False

    def _open(self, *_args) -> None:
        opt = self.option
        if opt.kind == OptionKind.INSTALL_FLATPAK:
            from ..installers.runner import launch_detached
            launch_detached(["flatpak", "run", opt.target])
            return
        entry = self.win.app.resolver().catalog.get(opt.app_id) or {}
        for desktop_id in entry.get("linux", {}).get("desktop", ()):
            try:
                info = Gio.DesktopAppInfo.new(desktop_id)
            except TypeError:
                info = None
            if info:
                info.launch([], None)
                return
        self.win.toast(_("Installed; find it in the applications menu."))


# ---------------------------------------------------------------------------------------
class ScriptPage:
    def __init__(self, win: Window, report) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
        hints = [f for f in report.findings if f.code.startswith("script-")]
        if hints:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            card.add_css_class("alert-card")
            card.add_css_class("info")
            card.append(_label(_("Worth a look (hints, not a verdict):"), "heading"))
            for f in hints:
                card.append(_label("• " + finding_text(f)))
            box.append(card)
        box.append(_label(_("First lines of the file, shown as text. Nothing was run."), "dim-label", "caption"))
        view = Gtk.TextView(editable=False, monospace=True, cursor_visible=False, vexpand=True,
                            wrap_mode=Gtk.WrapMode.WORD_CHAR)
        view.add_css_class("script-view")
        view.add_css_class("card")
        view.get_buffer().set_text(report.preview)
        box.append(view)
        self.page = win._page(_("Content"), "script", box)


class SearchPage:
    def __init__(self, win: Window) -> None:
        self.win = win
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
        self.entry = Gtk.SearchEntry(placeholder_text=_("A Windows program, e.g. Photoshop"))
        self.entry.connect("search-changed", self._changed)
        box.append(self.entry)
        self.results = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.results.add_css_class("boxed-list")
        self.results.set_placeholder(_label(_("Type a program name to see its Linux options."),
                                            "dim-label", xalign=0.5))
        box.append(self.results)
        self.page = win._page(_("Find an alternative"), "search", box)
        GLib.idle_add(lambda: self.entry.grab_focus() and False)

    def _changed(self, entry) -> None:
        while (child := self.results.get_first_child()) is not None:
            self.results.remove(child)
        text = entry.get_text().strip()
        if len(text) < 2:
            return
        for item in self.win.app.resolver().search(text)[:12]:
            from ..resolvers.resolver import _icon_for
            row = Adw.ActionRow(title=GLib.markup_escape_text(item["name"]),
                                subtitle=GLib.markup_escape_text(item.get("vendor", "")), activatable=True)
            row.add_prefix(_icon(_icon_for(item), 32))
            row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            row.connect("activated", lambda _r, e=item: self._open(e))
            self.results.append(row)

    def _open(self, entry) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                      margin_top=24, margin_bottom=24, margin_start=16, margin_end=16)
        page_title = entry["name"]
        from ..resolvers.resolver import _icon_for
        box.append(_icon(_icon_for(entry), 80))
        box.append(_label(entry["name"], "hero-title", xalign=0.5))
        if entry.get("message"):
            box.append(_label(pick(entry["message"]), xalign=0.5))
        spinner = Adw.Spinner(height_request=32)
        box.append(spinner)
        page = self.win._page(page_title, "entry", box)
        self.win.nav.push(page)

        def work():
            options = self.win.app.resolver().entry_analysis(entry["id"])
            GLib.idle_add(fill, options)

        def fill(options):
            box.remove(spinner)
            if not options:
                box.append(_label(_("No Linux option is known for this program yet."), "dim-label", xalign=0.5))
                return False
            same = [o for o in options if o.relation == Relation.SAME]
            other = [o for o in options if o.relation != Relation.SAME]
            fake = ResultPage.__new__(ResultPage)
            fake.win = self.win
            for title, items in ((_("Same program"), same), (_("Alternatives"), other)):
                if items:
                    group = Adw.PreferencesGroup(title=title)
                    for opt in items:
                        group.add(ResultPage._row(fake, opt))
                    box.append(group)
            if other and not same:
                box.append(_label(_("These are different programs with a similar purpose, not "
                                    "Linux versions of {name}.").format(name=entry["name"]),
                                  "dim-label", "caption"))
            return False

        threading.Thread(target=work, daemon=True).start()


class HistoryPage:
    def __init__(self, win: Window) -> None:
        self.win = win
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                           margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
        clear = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text=_("Clear history"))
        clear.connect("clicked", self._clear)
        self._fill()
        self.page = win._page(_("History"), "history", self.box, header_end=[clear])

    def _fill(self) -> None:
        while (child := self.box.get_first_child()) is not None:
            self.box.remove(child)
        items = history.entries()
        if not items:
            self.box.append(Adw.StatusPage(icon_name="document-open-recent-symbolic",
                                           title=_("No history"),
                                           description=_("Analyzed files and your choices appear here. "
                                                         "Only file names are kept, never folders.")))
            return
        listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        listbox.add_css_class("boxed-list")
        catalog = self.win.app.resolver().catalog
        for item in items[:200]:
            when = GLib.DateTime.new_from_unix_local(int(item.get("time", 0))).format("%x %H:%M")
            app = catalog.get(item.get("app", "")) if item.get("app") else None
            sub = " · ".join(x for x in (when, app["name"] if app else "", item.get("action", ""),
                                          item.get("result", "")) if x)
            row = Adw.ActionRow(title=GLib.markup_escape_text(display_name(str(item.get("file", "?")))),
                                subtitle=GLib.markup_escape_text(sub))
            listbox.append(row)
        self.box.append(listbox)

    def _clear(self, *_args) -> None:
        history.clear()
        self._fill()
        self.win.toast(_("History cleared"))
