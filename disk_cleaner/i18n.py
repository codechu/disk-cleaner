"""i18n setup — gettext-based message translation.

Kaynak kod İngilizce; çeviriler ``po/*.po``'da. ``LANG`` / ``LC_MESSAGES`` env
değişkenine bakar; uygulama hiçbir çeviri bulamazsa İngilizce'ye düşer.

Usage:
    from disk_cleaner.i18n import _

    print(_("Smart scan"))            # → "Akıllı tara" (tr), "Smart scan" (en)
    print(_("{n} items").format(n=3)) # markup placeholder, çeviri sonrası format
"""
from __future__ import annotations

import gettext as _gettext
import os
from pathlib import Path

# Bu paketin yanındaki ``locale/`` dizini — pyproject ile install edildiğinde
# /usr/share/locale/ altına gider; lokal geliştirmede paket içinde aranır.
_PACKAGE_DIR = Path(__file__).parent
_LOCAL_LOCALE = _PACKAGE_DIR / "locale"
_SYSTEM_LOCALE = Path("/usr/share/locale")

_DOMAIN = "disk_cleaner"


def _resolve_localedir() -> Path:
    """Önce paket-içi locale (geliştirme), sonra sistem locale (kurulu)."""
    if _LOCAL_LOCALE.is_dir():
        return _LOCAL_LOCALE
    return _SYSTEM_LOCALE


def _resolve_language() -> str | None:
    """Üç-katmanlı dil seçimi (yüksek öncelik ilk):

    1. ``DISK_CLEANER_LANG`` env override (dev/test/CI)
    2. ``settings.json`` içindeki ``language`` anahtarı (kullanıcı tercihi)
    3. ``None`` → gettext kendi ``LANG``/``LC_MESSAGES`` çözümlemesini yapar
    """
    if lang := os.environ.get("DISK_CLEANER_LANG"):
        return lang
    # Settings.json'u raw oku — settings.py import etmek circular yaratabilir
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
    """Çeviri nesnesi kur — yoksa NullTranslations (İngilizce passthrough)."""
    localedir = _resolve_localedir()
    lang = _resolve_language()
    languages = [lang] if lang else None
    try:
        return _gettext.translation(_DOMAIN, localedir=str(localedir),
                                     languages=languages, fallback=True)
    except Exception:
        return _gettext.NullTranslations()


_translation = _build_translation()
_ = _translation.gettext
ngettext = _translation.ngettext


def reload_translations(lang: str | None = None) -> None:
    """Runtime'da dil değiştirmek için — yeni LANG'la çevirileri yeniden yükle.

    Mevcut process'te alınmış ``_`` referansları eski kalır; yeni stringler
    yeni çeviri tarafından döner. Settings UI'sından çağrılır.
    """
    global _translation, _, ngettext
    if lang:
        os.environ["DISK_CLEANER_LANG"] = lang
    _translation = _build_translation()
    _ = _translation.gettext
    ngettext = _translation.ngettext


__all__ = ["_", "ngettext", "reload_translations"]
