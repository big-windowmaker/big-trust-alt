"""Text formats: shell scripts, Windows scripts, .flatpakref, self-extracting installers."""

from __future__ import annotations

import configparser
import re

MAX_PREVIEW = 64 * 1024
PREVIEW_LINES = 200

# Patterns worth pointing out in a script. They are hints for the reader,
# not a verdict: plenty of honest installers use sudo or curl.
RISKY = (
    ("download-and-run", re.compile(r"(curl|wget)[^\n|;]*\|\s*(sudo\s+)?(ba|z|da)?sh\b")),
    ("privilege", re.compile(r"(^|[\s;&|(])(sudo|pkexec|doas|su\s+-c)\s")),
    ("recursive-delete", re.compile(r"\brm\s+-[a-zA-Z]*[rf][a-zA-Z]*\s+(/|~|\$HOME)")),
    ("disk-write", re.compile(r"\b(dd\s+if=|mkfs(\.\w+)?\s|wipefs|fdisk|parted)\b")),
    ("system-files", re.compile(r"(>|tee\s+-a?\s*)\s*/(etc|usr|boot|lib)/")),
    ("world-writable", re.compile(r"\bchmod\s+(-R\s+)?0?777\b")),
    ("obfuscation", re.compile(r"(base64\s+(-d|--decode)|\beval\s+\"?\$\(|\\x[0-9a-f]{2}\\x[0-9a-f]{2})", re.I)),
    ("persistence", re.compile(r"(crontab|systemctl\s+enable|/etc/rc\.local|\.bashrc|\.profile|autostart)")),
    ("binary-payload", re.compile(r"^__ARCHIVE_BELOW__|^PAYLOAD:|MAKESELF", re.M)),
)
SHEBANG = re.compile(rb"^#!\s*(/\S+)(?:\s+(\S+))?")


def is_text(sample: bytes) -> bool:
    if b"\0" in sample[:8192]:
        return False
    try:
        sample[:8192].decode("utf-8")
    except UnicodeDecodeError as exc:
        # A multibyte sequence cut at the end of the sample is still text.
        return exc.start >= len(sample[:8192]) - 4
    return True


def interpreter(head: bytes) -> str:
    m = SHEBANG.match(head)
    if not m:
        return ""
    prog = m.group(1).decode("utf-8", "replace").rsplit("/", 1)[-1]
    if prog == "env" and m.group(2):
        prog = m.group(2).decode("utf-8", "replace")
    return prog[:40]


def preview(sample: bytes) -> tuple[str, list[str]]:
    text = sample[:MAX_PREVIEW].decode("utf-8", "replace")
    lines = text.splitlines()[:PREVIEW_LINES]
    shown = "\n".join(lines)
    hints = [code for code, rx in RISKY if rx.search(text)]
    return shown, hints


def is_makeself(sample: bytes) -> bool:
    return b"Makeself" in sample[:16384] or b"MS_dd_Progress" in sample[:16384]


def parse_flatpakref(text: str) -> dict[str, str]:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.read_string(text[:16384])
    section = "Flatpak Ref"
    if not parser.has_section(section):
        raise ValueError("not a flatpakref")
    info = {}
    for key in ("Name", "Branch", "Url", "Title", "IsRuntime", "Homepage", "SuggestRemoteName"):
        if parser.has_option(section, key):
            info[f"flatpakref.{key}"] = parser.get(section, key).strip()[:300]
    return info
