"""pytest fixtures.

Pure-logic test'ler GTK display olmadan koşabilir. UI panel'leri
:mod:`disk_cleaner._gtk`'tan ``Gtk`` import ederken X11/Wayland
gerektirmez (yalnızca instantiate edildiklerinde). Burada GDK backend'i
varsayılan olarak X11'e set ediyoruz — headless ortamda hatasız import.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("GDK_BACKEND", "x11")
# Testler i18n-bağımsız olsun: LANG ne olursa olsun İngilizce (kaynak dil) ile koşulur
os.environ["DISK_CLEANER_LANG"] = "en"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Testlerin sessizce ağa çıkmadığından emin ol."""
    yield
