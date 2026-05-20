# SPDX-License-Identifier: GPL-3.0-or-later

"""i18n setup — gettext-based message translation.

Source code is in English; translations live in ``po/*.po``. Looks at
the ``LANG`` / ``LC_MESSAGES`` environment variables; falls back to
English when no translation is available.

Usage:
    from disk_cleaner.i18n import _

    print(_("Smart scan"))            # → "Akıllı tara" (tr), "Smart scan" (en)
    print(_("{n} items").format(n=3)) # markup placeholder, format after translation
"""

from __future__ import annotations

import gettext as _gettext
import os
from pathlib import Path

# ``locale/`` directory next to this package — when installed via
# pyproject it lands under /usr/share/locale/; during local development
# it is looked up inside the package.
_PACKAGE_DIR = Path(__file__).parent
_LOCAL_LOCALE = _PACKAGE_DIR / "locale"
_SYSTEM_LOCALE = Path("/usr/share/locale")

_DOMAIN = "disk_cleaner"


def _resolve_localedir() -> Path:
    """In-package locale first (development), then system locale (installed)."""
    if _LOCAL_LOCALE.is_dir():
        return _LOCAL_LOCALE
    return _SYSTEM_LOCALE


def _resolve_language() -> str | None:
    """Three-layer language selection (highest priority first):

    1. ``DISK_CLEANER_LANG`` env override (dev/test/CI)
    2. ``language`` key in ``settings.json`` (user preference)
    3. ``None`` → gettext performs its own ``LANG``/``LC_MESSAGES``
       resolution
    """
    if lang := os.environ.get("DISK_CLEANER_LANG"):
        return lang
    # Read settings.json raw — importing settings.py could cause a cycle
    try:
        from .config import SETTINGS_FILE

        if SETTINGS_FILE.exists():
            import json

            with open(SETTINGS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if lang := data.get("language"):
                return lang
    except Exception:
        pass
    return None


def _build_translation() -> _gettext.NullTranslations:
    """Build a translation object — fall back to NullTranslations (English passthrough)."""
    localedir = _resolve_localedir()
    lang = _resolve_language()
    languages = [lang] if lang else None
    try:
        return _gettext.translation(
            _DOMAIN, localedir=str(localedir), languages=languages, fallback=True
        )
    except Exception:
        return _gettext.NullTranslations()


_translation = _build_translation()
_ = _translation.gettext
ngettext = _translation.ngettext


def reload_translations(lang: str | None = None) -> None:
    """Change language at runtime — reload translations with a new LANG.

    Existing ``_`` references in the running process stay bound to the
    old translator; new strings are resolved by the new one. Called
    from the Settings UI.
    """
    global _translation, _, ngettext
    if lang:
        os.environ["DISK_CLEANER_LANG"] = lang
    _translation = _build_translation()
    _ = _translation.gettext
    ngettext = _translation.ngettext


__all__ = ["_", "ngettext", "reload_translations"]
