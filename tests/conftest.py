"""pytest fixtures.

Pure-logic tests can run without a GTK display. UI panels do not need
X11/Wayland when importing ``Gtk`` from :mod:`disk_cleaner._gtk` — only
when instantiated. Here we default the GDK backend to X11 so imports
work in headless environments.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("GDK_BACKEND", "x11")
# Keep tests i18n-independent: regardless of LANG, run in English (the source language)
os.environ["DISK_CLEANER_LANG"] = "en"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Ensure tests do not silently go to the network."""
    yield
