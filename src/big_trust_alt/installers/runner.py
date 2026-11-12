"""Carry out an Option chosen by the user.

* Package changes go through Pamac (pamac-installer shows the transaction
  and asks Polkit) or Flatpak (its system helper asks Polkit). Big Trust Alt
  itself never runs as root.
* Running the original file needs an explicit confirmation from the UI and
  is refused if the file changed since it was analyzed.
* The result is verified afterwards (pacman -Q / flatpak info).
"""

from __future__ import annotations

import os
import shutil
import signal
import stat
import subprocess
import threading
from dataclasses import dataclass
from enum import StrEnum
from collections.abc import Callable

from ..core.model import FileIdentity, Option, OptionKind
from ..i18n import _
from ..security.fileinfo import verify_unchanged

TERMINALS = (
    ("xdg-terminal-exec", []), ("big-wm-terminal", ["-e"]), ("x-terminal-emulator", ["-e"]),
    ("konsole", ["--noclose", "-e"]), ("xfce4-terminal", ["--hold", "-x"]),
    ("gnome-terminal", ["--"]), ("kgx", ["--"]), ("foot", ["--hold"]), ("alacritty", ["--hold", "-e"]),
    ("xterm", ["-hold", "-e"]),
)


class Outcome(StrEnum):
    DONE = "done"            # finished and verified
    LAUNCHED = "launched"    # handed to another program; we cannot verify the end
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUSED = "refused"      # safety check failed


@dataclass
class Result:
    outcome: Outcome
    message: str = ""


class Job:
    """One running action. Callbacks are called from a worker thread."""

    def __init__(self, option: Option, on_line: Callable[[str], None] | None = None) -> None:
        self.option = option
        self.on_line = on_line or (lambda _line: None)
        self._proc: subprocess.Popen | None = None
        self._cancelled = threading.Event()

    @property
    def cancellable(self) -> bool:
        return self.option.kind in (OptionKind.INSTALL_FLATPAK, OptionKind.INSTALL_FLATPAKREF)

    def cancel(self) -> None:
        self._cancelled.set()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass

    def _stream(self, cmd: list[str]) -> int:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      stdin=subprocess.DEVNULL, text=True, bufsize=1, env=env,
                                      errors="replace")
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            line = line.rstrip()
            if line:
                self.on_line(line[-300:])
        return self._proc.wait()

    def run(self) -> Result:
        kind, target = self.option.kind, self.option.target
        try:
            if kind in (OptionKind.INSTALL_REPO, OptionKind.INSTALL_AUR, OptionKind.INSTALL_PACKAGE_FILE):
                return self._pamac(kind, target)
            if kind in (OptionKind.INSTALL_FLATPAK, OptionKind.INSTALL_FLATPAKREF):
                return self._flatpak()
        except OSError as exc:
            return Result(Outcome.FAILED, str(exc))
        return Result(Outcome.FAILED, f"not a background job: {kind}")

    def _pamac(self, kind: OptionKind, target: str) -> Result:
        if not shutil.which("pamac-installer"):
            return Result(Outcome.FAILED, _("Pamac is not installed."))
        cmd = ["pamac-installer"]
        if kind == OptionKind.INSTALL_AUR:
            cmd.append("--build")
        cmd += ["--", target] if kind != OptionKind.INSTALL_AUR else [target]
        self.on_line(_("Review the changes in the Pamac window…"))
        code = self._stream(cmd)
        if kind == OptionKind.INSTALL_PACKAGE_FILE:
            return Result(Outcome.DONE if code == 0 else Outcome.FAILED)
        if code != 0:
            return Result(Outcome.CANCELLED if code == 1 and self._cancelled.is_set() else Outcome.FAILED,
                          _("Pamac did not apply the changes (cancelled or failed)."))
        ok = subprocess.run(["pacman", "-Q", target], capture_output=True, check=False).returncode == 0
        return Result(Outcome.DONE if ok else Outcome.FAILED,
                      "" if ok else _("Pamac finished, but the package is not installed."))

    def _flatpak(self) -> Result:
        opt = self.option
        if not shutil.which("flatpak"):
            return Result(Outcome.FAILED, _("Flatpak is not installed on this system."))
        if opt.kind == OptionKind.INSTALL_FLATPAKREF:
            flag = "--bundle" if opt.target.endswith(".flatpak") else "--from"
            cmd = ["flatpak", "install", "--system", "-y", "--noninteractive", flag, opt.target]
            app_id = ""
        else:
            remote = opt.command[-2] if len(opt.command) >= 2 else "flathub"
            app_id = opt.target
            cmd = ["flatpak", "install", "--system", "-y", "--noninteractive", remote, app_id]
        code = self._stream(cmd)
        if self._cancelled.is_set():
            return Result(Outcome.CANCELLED, _("Installation cancelled. Flatpak removes partial downloads."))
        if code != 0:
            return Result(Outcome.FAILED, _("Flatpak reported an error (code {code}).").format(code=code))
        if app_id:
            ok = subprocess.run(["flatpak", "info", app_id], capture_output=True, check=False).returncode == 0
            if not ok:
                return Result(Outcome.FAILED, _("Flatpak finished, but the app is not installed."))
        return Result(Outcome.DONE)


def launch_detached(cmd: list[str], cwd: str | None = None) -> None:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True, env=env)


def find_terminal() -> list[str]:
    for name, args in TERMINALS:
        if shutil.which(name):
            return [name, *args]
    return []


def run_original(option: Option, identity: FileIdentity | None, make_executable: bool,
                 in_terminal: bool) -> Result:
    """Run the analyzed file itself (native, Wine, Bottles, Java), after re-checking it."""
    path = option.target
    if identity is None or not verify_unchanged(path, identity):
        return Result(Outcome.REFUSED, _("The file changed after it was analyzed. Analyze it again."))
    cmd = list(option.command)
    if option.kind == OptionKind.RUN_NATIVE:
        mode = os.stat(path).st_mode
        if not mode & stat.S_IXUSR:
            if not make_executable:
                return Result(Outcome.REFUSED, _("The file is not executable. Allow it to be run first."))
            os.chmod(path, mode | stat.S_IXUSR)
        cmd = [path]
    tool = cmd[0]
    if tool in ("wine", "java", "flatpak") and not shutil.which(tool):
        return Result(Outcome.FAILED, _("{tool} is not installed.").format(tool=tool))
    if in_terminal:
        terminal = find_terminal()
        if not terminal:
            return Result(Outcome.FAILED, _("No terminal emulator was found."))
        cmd = [*terminal, *cmd]
    try:
        launch_detached(cmd, cwd=os.path.dirname(path) or None)
    except OSError as exc:
        return Result(Outcome.FAILED, str(exc))
    return Result(Outcome.LAUNCHED)
