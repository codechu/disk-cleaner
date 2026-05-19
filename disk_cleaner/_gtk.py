"""Ortak Gtk/Gdk setup — tek noktada ``gi.require_version`` çağrısı.

UI modülleri ``from .._gtk import Gtk, Gdk, GLib, Pango`` ile çeker.
``cairo`` import'u foreign-struct converter kaydı için gereklidir
(Gdk.cairo_create vb. fonksiyonlar buna güvenir).
"""
from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

try:  # noqa: SIM105
    import cairo  # noqa: F401  — converter kaydı için import yeterli
    _ = cairo.Context
except ImportError:
    pass

__all__ = ["Gdk", "GLib", "Gtk", "Pango"]
