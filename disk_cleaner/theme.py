"""Dark / light theme detection + user-preference override.

Three layers (highest priority first):
1. ``theme`` key in ``settings.json``: ``"light"`` / ``"dark"`` / ``"auto"``
2. GTK ``Gtk.Settings`` property ``gtk-application-prefer-dark-theme``
3. If the GTK theme name contains ``dark``, dark mode is assumed
"""
from __future__ import annotations

from ._gtk import Gtk


def _user_theme_pref() -> str:
    """User preference from settings.json — default ``"auto"``."""
    try:
        from .settings import SETTINGS
        return SETTINGS.get("theme", "auto")
    except Exception:
        return "auto"


def _gtk_dark() -> bool:
    """Dark mode according to the system GTK theme (assuming no override)."""
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
    """Is dark mode active? Includes user override."""
    pref = _user_theme_pref()
    if pref == "dark":
        return True
    if pref == "light":
        return False
    return _gtk_dark()


def apply_user_preference() -> None:
    """Inform GTK of the user preference — new windows open in the right theme."""
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
