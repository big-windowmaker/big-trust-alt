#!/usr/bin/env python3
"""Regenerate po/big-trust-alt.pot and po/pt_BR.po, then compile build/locale."""

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from pt_BR import T  # noqa: E402


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def main() -> int:
    sources = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "src").rglob("*.py"))
    subprocess.run(["xgettext", "--language=Python", "--keyword=_", "--keyword=ngettext:1,2",
                    "--from-code=UTF-8", "--package-name=big-trust-alt", "--package-version=0.1.0",
                    "--msgid-bugs-address=https://github.com/big-windowmaker/big-trust-alt/issues",
                    "-o", "po/big-trust-alt.pot", *sources], cwd=ROOT, check=True)
    potfile = ROOT / "po/big-trust-alt.pot"
    potfile.write_text(potfile.read_text(encoding="utf-8").replace("charset=CHARSET", "charset=UTF-8"), encoding="utf-8")
    pot = potfile.read_text(encoding="utf-8").split("\n\n", 1)[1]
    header = ('msgid ""\nmsgstr ""\n"Project-Id-Version: big-trust-alt\\n"\n"PO-Revision-Date: 2026-11-12 00:00-0300\\n"\n"Last-Translator: Rafael Ruscher <rruscher@gmail.com>\\n"\n"Language-Team: Portuguese (Brazil)\\n"\n"Language: pt_BR\\n"\n'
              '"MIME-Version: 1.0\\n"\n"Content-Type: text/plain; charset=UTF-8\\n"\n'
              '"Content-Transfer-Encoding: 8bit\\n"\n"Plural-Forms: nplurals=2; plural=(n > 1);\\n"\n\n')
    missing = []

    def fill(m: re.Match) -> str:
        block = m.group(1)
        msgid = "".join(ast.literal_eval(line) for line in block.strip().split("\n"))
        tr = T.get(msgid)
        if tr is None:
            missing.append(msgid)
            tr = ""
        return f'msgid {block}msgstr "{esc(tr)}"\n'

    body = re.sub(r'^msgid ((?:".*"\n)+)msgstr ""\n', fill, pot, flags=re.M)
    (ROOT / "po/pt_BR.po").write_text(header + body, encoding="utf-8")
    out = ROOT / "build/locale/pt_BR/LC_MESSAGES"
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["msgfmt", "--check", "-o", str(out / "big-trust-alt.mo"), "po/pt_BR.po"], cwd=ROOT, check=True)
    if missing:
        print("untranslated:", *missing, sep="\n  ", file=sys.stderr)
        return 1
    print(f"pt_BR: {len(T)} translations, 0 missing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
