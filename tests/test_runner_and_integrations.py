import json
import os
import subprocess

import pytest
from builders import build_appimage, build_pe

from big_trust_alt.core import history
from big_trust_alt.core.model import Option, OptionKind, Relation
from big_trust_alt.detectors import analyze_file
from big_trust_alt.installers import runner
from big_trust_alt.integrations import mime
from big_trust_alt.security.fileinfo import verify_unchanged


@pytest.fixture
def launches(monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "launch_detached", lambda cmd, cwd=None: calls.append(cmd))
    return calls


def _option(kind, path, command):
    return Option(kind=kind, relation=Relation.ORIGINAL, app_id="", title="x", target=path, command=command)


def test_changed_file_is_refused(write, launches):
    path = write("App.AppImage", build_appimage(), mode=0o755)
    report = analyze_file(path)
    with open(path, "ab") as fh:
        fh.write(b"tampered")
    assert not verify_unchanged(path, report.identity)
    result = runner.run_original(_option(OptionKind.RUN_NATIVE, path, [path]), report.identity, True, False)
    assert result.outcome == runner.Outcome.REFUSED and not launches


def test_replaced_file_same_content_other_inode_is_refused(write, launches):
    path = write("App.AppImage", build_appimage(), mode=0o755)
    report = analyze_file(path)
    data = open(path, "rb").read()
    os.unlink(path)
    with open(path, "wb") as fh:
        fh.write(data)
    result = runner.run_original(_option(OptionKind.RUN_NATIVE, path, [path]), report.identity, True, False)
    assert result.outcome == runner.Outcome.REFUSED


def test_exec_bit_needs_consent(write, launches):
    path = write("App.AppImage", build_appimage(), mode=0o644)
    report = analyze_file(path)
    opt = _option(OptionKind.RUN_NATIVE, path, [path])
    assert runner.run_original(opt, report.identity, False, False).outcome == runner.Outcome.REFUSED
    assert not os.stat(path).st_mode & 0o100
    # chmod changes ctime, not mtime/inode/content: still the analyzed file.
    assert runner.run_original(opt, report.identity, True, False).outcome == runner.Outcome.LAUNCHED
    assert os.stat(path).st_mode & 0o100 and launches == [[path]]


def test_wine_command_is_an_argument_list(write, launches, monkeypatch):
    monkeypatch.setattr(runner.shutil, "which", lambda name: f"/usr/bin/{name}")
    path = write("a b;$(id).exe", build_pe({}))
    report = analyze_file(path)
    opt = _option(OptionKind.RUN_WINE, path, ["wine", path])
    assert runner.run_original(opt, report.identity, False, False).outcome == runner.Outcome.LAUNCHED
    assert launches == [["wine", path]]


def test_missing_wine(write, launches, monkeypatch):
    monkeypatch.setattr(runner.shutil, "which", lambda name: None)
    path = write("a.exe", build_pe({}))
    report = analyze_file(path)
    result = runner.run_original(_option(OptionKind.RUN_WINE, path, ["wine", path]), report.identity, False, False)
    assert result.outcome == runner.Outcome.FAILED and not launches


def test_flatpak_job_cancel_reports_real_state(monkeypatch):
    lines = []
    script = "import time,sys\nprint('Installing 10%', flush=True)\ntime.sleep(5)\n"

    class FakeJob(runner.Job):
        def _flatpak(self):
            code = self._stream(["python3", "-c", script])
            if self._cancelled.is_set():
                return runner.Result(runner.Outcome.CANCELLED)
            return runner.Result(runner.Outcome.DONE if code == 0 else runner.Outcome.FAILED)

    opt = Option(kind=OptionKind.INSTALL_FLATPAK, relation=Relation.SAME, app_id="x", title="x", target="org.x.X")
    job = FakeJob(opt, on_line=lambda line: (lines.append(line), job.cancel()))
    result = job.run()
    assert result.outcome == runner.Outcome.CANCELLED and lines[0] == "Installing 10%"


def test_mime_associate_and_restore(tmp_path):
    path = mime.mimeapps_path()
    path.parent.mkdir(parents=True)
    path.write_text("[Default Applications]\napplication/x-msdownload=wine.desktop;\ntext/plain=kate.desktop;\n"
                    "[Added Associations]\napplication/vnd.debian.binary-package=big-pkg-installer.desktop;\n")
    changed = mime.associate()
    assert "application/x-msdownload" in changed
    text = path.read_text()
    assert "application/x-msdownload=io.github.big_windowmaker.BigTrustAlt.desktop;" in text
    assert "big-pkg-installer.desktop;io.github.big_windowmaker.BigTrustAlt.desktop;" in text
    assert "text/plain=kate.desktop;" in text
    mime.dissociate()
    text = path.read_text()
    assert "application/x-msdownload=wine.desktop;" in text
    assert "BigTrustAlt" not in text
    assert "application/vnd.debian.binary-package=big-pkg-installer.desktop;" in text


def test_history_keeps_names_not_paths(tmp_path):
    history.record("/home/someone/Downloads/ChromeSetup.exe", "ab" * 32, "exe", "google-chrome", "analyze", "probable")
    items = history.entries()
    assert items[0]["file"] == "ChromeSetup.exe"
    raw = history.history_path().read_text()
    assert "/home/" not in raw
    assert oct(history.history_path().stat().st_mode & 0o777) == "0o600"
    history.clear()
    assert history.entries() == []


def test_cli_json(write, tmp_path):
    path = write("SpotifySetup.exe", build_pe({"ProductName": "Spotify", "CompanyName": "Spotify Ltd"}))
    env = dict(os.environ, PYTHONPATH=str(os.path.join(os.path.dirname(__file__), "..", "src")))
    out = subprocess.run(["python3", "-m", "big_trust_alt", "--analyze", path, "--json", "--offline"],
                         capture_output=True, text=True, env=env, check=False)
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert data["file"]["format"] == "exe" and data["level"] in ("confirmed", "probable", "unknown")
    missing = subprocess.run(["python3", "-m", "big_trust_alt", "--analyze", str(tmp_path / "nope.exe")],
                             capture_output=True, text=True, env=env, check=False)
    assert missing.returncode == 2 and "does not exist" in missing.stderr
