import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from big_trust_alt.providers import (AurPackage, DesktopApp, ProviderUnavailable,  # noqa: E402
                                     RepoPackage)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Never touch the real user's config, history or mimeapps.list."""
    for var, sub in (("XDG_CONFIG_HOME", "config"), ("XDG_STATE_HOME", "state"), ("XDG_DATA_HOME", "data")):
        monkeypatch.setenv(var, str(tmp_path / sub))
    monkeypatch.setenv("LANGUAGE", "en")
    yield


@pytest.fixture
def catalog():
    return _fixture_catalog()


def _fixture_catalog():
    from big_trust_alt.database.catalog import Catalog
    import json
    from big_trust_alt.database.schema import validate_catalog, validate_document
    doc = json.loads((ROOT / "tests/fixtures/catalog/test.json").read_text())
    entries = validate_document(doc)
    validate_catalog(entries)
    return Catalog(entries={e["id"]: e for e in entries})


class FakeRepos:
    def __init__(self, sync=None, installed=(), broken=False):
        self.sync = sync or {}
        self.local = set(installed)
        self.broken = broken

    def get(self, name):
        if self.broken:
            raise ProviderUnavailable("pacman")
        if name in self.sync:
            return RepoPackage(name, self.sync[name], "1.0", name in self.local)
        return None

    def installed(self, name):
        return name in self.local

    def refresh_installed(self):
        pass


class FakeAur:
    def __init__(self, known=(), offline=False):
        self.known = set(known)
        self.offline = offline

    def info(self, names):
        if self.offline:
            raise ProviderUnavailable("offline")
        return {n: AurPackage(n, "1", 10, 1.0, "someone", False, "") if n in self.known else None for n in names}


class FakeFlatpak:
    def __init__(self, remote=(), installed=(), present=True):
        self.remote = set(remote)
        self.inst = set(installed)
        self.present = present

    def available(self):
        return self.present

    def remote_of(self, app_id):
        if not self.present:
            raise ProviderUnavailable("flatpak")
        return "flathub" if app_id in self.remote else ""

    def installed(self, app_id):
        if not self.present:
            raise ProviderUnavailable("flatpak")
        return app_id in self.inst

    def refresh(self):
        pass


class FakeDesktop:
    def __init__(self, apps=()):
        self.apps = set(apps)

    def find(self, desktop_id):
        return DesktopApp(desktop_id, desktop_id, "", "/x") if desktop_id in self.apps else None


class FakeTools:
    def __init__(self, **present):
        self.present = present

    def __getattr__(self, name):
        return self.__dict__["present"].get(name, "")


class FakeSystem:
    def __init__(self, repos=None, aur=None, flatpak=None, desktop=None, tools=None):
        self.repos = repos or FakeRepos()
        self.aur = aur or FakeAur()
        self.flatpak = flatpak or FakeFlatpak()
        self.desktop = desktop or FakeDesktop()
        self.tools = tools or FakeTools()


@pytest.fixture
def write(tmp_path):
    def _write(name, data, mode=0o644):
        path = tmp_path / "files" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode())
        os.chmod(path, mode)
        return str(path)
    return _write
