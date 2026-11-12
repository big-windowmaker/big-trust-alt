"""Static checks of the UI code (it needs a display to run)."""

import ast
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "src" / "big_trust_alt" / "ui"


def test_idle_callbacks_are_not_bool_returning_methods():
    """GLib.idle_add(widget.grab_focus) loops forever: grab_focus() returns True."""
    bad = []
    for path in UI.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", "") in ("idle_add", "timeout_add"):
                cb = node.args[-1] if node.func.attr == "timeout_add" else node.args[0]
                if isinstance(cb, ast.Attribute) and cb.attr in ("grab_focus", "activate", "set_visible", "present"):
                    bad.append(f"{path.name}:{node.lineno}")
    assert not bad, bad
