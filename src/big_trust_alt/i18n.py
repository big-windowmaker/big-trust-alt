"""gettext setup and the language used for catalog texts."""

from __future__ import annotations

import gettext
import locale
import os
from pathlib import Path

DOMAIN = "big-trust-alt"
_DEV_LOCALE = Path(__file__).resolve().parents[2] / "build" / "locale"


def _localedir() -> str:
    if os.environ.get("BIG_TRUST_ALT_LOCALEDIR"):
        return os.environ["BIG_TRUST_ALT_LOCALEDIR"]
    if _DEV_LOCALE.is_dir():
        return str(_DEV_LOCALE)
    return "/usr/share/locale"


try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    pass
LOCALEDIR = _localedir()
_translation = gettext.translation(DOMAIN, LOCALEDIR, fallback=True)
_ = _translation.gettext
ngettext = _translation.ngettext


def bind_gtk() -> None:
    """Let GtkBuilder/libadwaita pick the same domain (called by the UI)."""
    try:
        locale.bindtextdomain(DOMAIN, LOCALEDIR)
        locale.textdomain(DOMAIN)
    except AttributeError:
        pass


def catalog_lang() -> str:
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value:
            return "pt_BR" if value.lower().startswith("pt") else "en"
    return "en"


def pick(texts: dict | None) -> str:
    if not texts:
        return ""
    return texts.get(catalog_lang()) or texts.get("en", "")
