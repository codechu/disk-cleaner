"""Karanlık / aydınlık tema algılama + kullanıcı tercih override'ı.

Üç-katmanlı (yüksek öncelik ilk):
1. ``settings.json`` ``theme`` anahtarı: ``"light"`` / ``"dark"`` / ``"auto"``
2. GTK ``Gtk.Settings`` özelliği ``gtk-application-prefer-dark-theme``
3. GTK tema adında ``dark`` geçerse dark mode kabul edilir
"""
from __future__ import annotations

from ._gtk import Gtk


def _user_theme_pref() -> str:
    """settings.json'dan kullanıcı tercihi — default ``"auto"``."""
    try:
        from .settings import SETTINGS
        return SETTINGS.get("theme", "auto")
    except Exception:
        return "auto"


def _gtk_dark() -> bool:
    """GTK sistem temasına göre dark mode mu (override yok varsayımı)."""
    try:
        s = Gtk.Settings.get_default()
        if s is None:
            return False
        if s.get_property("gtk-application-prefer-dark-theme"):
            return True
        name = (s.get_property("gtk-theme-name") or "").lower()
        return "dark" in name
    except Exception:
        return False


def is_dark_theme() -> bool:
    """Dark mode aktif mi? Kullanıcı override'ı ile birlikte."""
    pref = _user_theme_pref()
    if pref == "dark":
        return True
    if pref == "light":
        return False
    return _gtk_dark()


def apply_user_preference() -> None:
    """Kullanıcı tercihini GTK'ya bildir — yeni pencereler doğru tema açar."""
    pref = _user_theme_pref()
    if pref == "auto":
        return  # GTK system default
    try:
        s = Gtk.Settings.get_default()
        if s is not None:
            s.set_property("gtk-application-prefer-dark-theme", pref == "dark")
    except Exception:
        pass


__all__ = ["is_dark_theme", "apply_user_preference"]
