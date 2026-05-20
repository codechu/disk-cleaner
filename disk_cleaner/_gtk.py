# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared Gtk/Gdk setup — single point for the ``gi.require_version`` call.

UI modules pull these via ``from .._gtk import Gtk, Gdk, GLib, Pango``.
Importing ``cairo`` is required to register the foreign-struct
converter (functions like Gdk.cairo_create depend on it).
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

try:  # noqa: SIM105
    import cairo  # noqa: F401  — importing it is enough to register the converter

    _ = cairo.Context
except ImportError:
    pass

__all__ = ["Gdk", "GLib", "Gtk", "Pango"]
