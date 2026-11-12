from builders import build_appimage, build_deb, build_msi, build_pe, build_rpm
from conftest import FakeAur, FakeDesktop, FakeFlatpak, FakeRepos, FakeSystem, FakeTools

from big_trust_alt.core.model import Level, OptionKind, Relation
from big_trust_alt.detectors import analyze_file
from big_trust_alt.resolvers.resolver import Preferences, Resolver

FULL = dict(
    repos=FakeRepos({"chromium": "extra", "firefox": "extra", "kate": "extra", "gimp": "extra", "7zip": "extra",
                     "spotify-launcher": "extra", "discord": "extra"}),
    aur=FakeAur({"google-chrome"}),
    flatpak=FakeFlatpak({"com.google.Chrome", "org.mozilla.firefox", "com.discordapp.Discord", "com.spotify.Client",
                         "com.github.dail8859.NotepadNext"}),
    tools=FakeTools(wine="/usr/bin/wine", big_pkg_installer="/usr/bin/big-pkg-installer-gui",
                    pamac_installer="/usr/bin/pamac-installer"),
)


def resolve(catalog, path, **system):
    params = dict(FULL)
    params.update(system)
    return Resolver(catalog, FakeSystem(**params), Preferences()).analyze(analyze_file(path))


def kinds(analysis):
    return [(o.kind, o.relation, o.target) for o in analysis.options]


def test_chrome_setup(catalog, write):
    a = resolve(catalog, write("ChromeSetup.exe", build_pe({"ProductName": "Google Installer (x86)",
                                                             "CompanyName": "Google LLC"})))
    assert a.level == Level.PROBABLE and a.entry_id == "google-chrome"
    assert a.recommended.kind == OptionKind.INSTALL_FLATPAK and a.recommended.relation == Relation.SAME
    assert (OptionKind.INSTALL_AUR, Relation.SAME, "google-chrome") in kinds(a)
    alt = [o for o in a.options if o.app_id == "chromium"][0]
    assert alt.relation == Relation.ALTERNATIVE and alt.note
    wine = [o for o in a.options if o.kind == OptionKind.RUN_WINE][0]
    assert wine.available and wine.experimental  # catalog says the Linux version is the way


def test_discord_confirmed_by_metadata(catalog, write):
    a = resolve(catalog, write("DiscordSetup.exe", build_pe({"ProductName": "Discord - https://discord.com/",
                                                              "CompanyName": "Discord Inc."})))
    assert a.level == Level.CONFIRMED and a.entry_id == "discord"
    assert a.recommended.kind == OptionKind.INSTALL_REPO and a.recommended.target == "discord"


def test_firefox_installed_opens_directly(catalog, write):
    a = resolve(catalog, write("Firefox Setup 133.0.exe", build_pe({"ProductName": "Firefox", "CompanyName": "Mozilla"})),
                desktop=FakeDesktop({"firefox.desktop"}))
    assert a.level == Level.CONFIRMED
    assert a.recommended.kind == OptionKind.OPEN_INSTALLED


def test_notepadpp_alternatives_only(catalog, write):
    a = resolve(catalog, write("npp.8.9.Installer.x64.exe", build_pe({"ProductName": "Notepad++"})))
    assert a.entry_id == "notepad-plus-plus"
    same = [o for o in a.options if o.relation == Relation.SAME]
    assert not same
    alts = {o.app_id for o in a.options if o.relation == Relation.ALTERNATIVE}
    assert alts == {"kate", "notepadnext"}
    assert a.recommended.relation == Relation.ALTERNATIVE and a.recommended.note


def test_spotify(catalog, write):
    a = resolve(catalog, write("SpotifySetup.exe", build_pe({"ProductName": "Spotify", "CompanyName": "Spotify Ltd"})))
    assert a.level == Level.CONFIRMED and a.recommended.target == "spotify-launcher"


def test_unknown_windows_installer(catalog, write):
    a = resolve(catalog, write("random_tool_v2.exe", build_pe({"ProductName": "Random"})))
    assert a.level == Level.UNKNOWN and a.recommended is None
    assert [o.kind for o in a.options] == [OptionKind.RUN_WINE]


def test_deb_prefers_native_before_conversion(catalog, write):
    a = resolve(catalog, write("google-chrome-stable_current_amd64.deb", build_deb("google-chrome-stable")))
    assert a.level == Level.CONFIRMED
    ranks = {o.kind: o.rank for o in a.options}
    assert ranks[OptionKind.INSTALL_FLATPAK] < ranks[OptionKind.CONVERT_PACKAGE]
    assert a.recommended.kind != OptionKind.CONVERT_PACKAGE


def test_rpm_uses_big_pkg_installer(catalog, write):
    a = resolve(catalog, write("unknown-1.0.x86_64.rpm", build_rpm("unknown-thing")))
    conv = [o for o in a.options if o.kind == OptionKind.CONVERT_PACKAGE][0]
    assert conv.available and conv.command[0] == "big-pkg-installer-gui"


def test_appimage_runs_only_on_request(catalog, write):
    a = resolve(catalog, write("Thing-x86_64.AppImage", build_appimage()))
    run = [o for o in a.options if o.kind == OptionKind.RUN_NATIVE]
    assert run and a.recommended is None


def test_unknown_script_never_recommended(catalog, write):
    a = resolve(catalog, write("install.sh", "#!/bin/sh\necho hi\n"))
    assert a.recommended is None
    assert [o.kind for o in a.options] == [OptionKind.RUN_NATIVE]


def test_without_wine(catalog, write):
    a = resolve(catalog, write("random.exe", build_pe({})), tools=FakeTools())
    wine = a.options[0]
    assert wine.kind == OptionKind.RUN_WINE and not wine.available and wine.unavailable_reason


def test_without_flatpak(catalog, write):
    a = resolve(catalog, write("SpotifySetup.exe", build_pe({"ProductName": "Spotify"})),
                flatpak=FakeFlatpak(present=False))
    fp = [o for o in a.options if o.kind == OptionKind.INSTALL_FLATPAK][0]
    assert not fp.available and "Flatpak" in fp.unavailable_reason
    assert a.recommended.kind == OptionKind.INSTALL_REPO


def test_offline_aur_still_answers(catalog, write):
    a = resolve(catalog, write("ChromeSetup.exe", build_pe({})), aur=FakeAur(offline=True))
    assert "aur" in a.providers_offline
    assert a.recommended.kind == OptionKind.INSTALL_FLATPAK


def test_ambiguous_does_not_choose(catalog, write):
    a = resolve(catalog, write("TwinSetup.exe", build_pe({})))
    assert a.level == Level.AMBIGUOUS and a.recommended is None
    assert {c.entry_id for c in a.candidates} == {"twin-a", "twin-b"}


def test_choosing_a_candidate(catalog, write):
    path = write("TwinSetup.exe", build_pe({}))
    system = FakeSystem(**FULL)
    system.repos.sync["twin-b"] = "community"
    a = Resolver(catalog, system).analyze(analyze_file(path), chosen="twin-b")
    assert a.entry_id == "twin-b" and a.recommended.target == "twin-b"


def test_msi_vendor_and_product(catalog, write):
    a = resolve(catalog, write("7z2501-x64.msi", build_msi("7-Zip (x64 edition) Package", "Igor Pavlov")))
    assert a.level == Level.CONFIRMED and a.entry_id == "7zip"
    wine = [o for o in a.options if o.kind == OptionKind.RUN_WINE][0]
    assert wine.command[:3] == ["wine", "msiexec", "/i"]


def test_photoshop_alternative_is_labelled(catalog, write):
    a = resolve(catalog, write("Photoshop_Set-Up.exe", build_pe({"ProductName": "Adobe Photoshop"})))
    assert a.recommended.app_id == "gimp" and a.recommended.relation == Relation.ALTERNATIVE


def test_malicious_name_stays_one_argument(catalog, write):
    name = "x; rm -rf ~ $(touch pwned) `id`.exe"
    a = resolve(catalog, write(name, build_pe({})))
    wine = [o for o in a.options if o.kind == OptionKind.RUN_WINE][0]
    assert wine.command[0] == "wine" and wine.command[1].endswith(name) and len(wine.command) == 2


def test_prefer_flatpak_and_hide_aur(catalog, write):
    path = write("DiscordSetup.exe", build_pe({"ProductName": "Discord"}))
    r = Resolver(catalog, FakeSystem(**FULL), Preferences(prefer_flatpak=True, show_aur=False))
    a = r.analyze(analyze_file(path))
    assert a.recommended.kind == OptionKind.INSTALL_FLATPAK
    a = r.analyze(analyze_file(write("ChromeSetup.exe", build_pe({}))))
    assert not [o for o in a.options if o.kind == OptionKind.INSTALL_AUR]


def test_search(catalog):
    r = Resolver(catalog, FakeSystem(**FULL))
    assert r.search("photoshop")[0]["id"] == "photoshop"
    opts = r.entry_analysis("photoshop")
    assert opts and opts[0].app_id == "gimp"


def test_installed_cli_tool_is_recommended_not_an_alternative(catalog, write):
    repos = FakeRepos({"7zip": "extra", "kate": "extra"}, installed={"7zip"})
    a = resolve(catalog, write("7z2501-x64.msi", build_msi("7-Zip (x64 edition) Package", "Igor Pavlov")), repos=repos)
    assert a.recommended.kind == OptionKind.OPEN_INSTALLED and a.recommended.relation == Relation.SAME
    assert not a.recommended.available and a.recommended.unavailable_reason
