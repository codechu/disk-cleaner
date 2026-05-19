"""Cleaner Strategy alt paketi.

Üç temel implementasyon hazır: :class:`SafePathCleaner` (tek yol),
:class:`ContentsCleaner` (dizin içeriği), :class:`CommandCleaner`
(shell/argv). Yeni bir temizlik türü eklemek için :class:`Cleaner`
ABC'sini implement et.
"""
from __future__ import annotations

from .base import Cleaner
from .command import CommandCleaner
from .contents import ContentsCleaner
from .safe_path import SafePathCleaner

__all__ = ["Cleaner", "CommandCleaner", "ContentsCleaner", "SafePathCleaner"]
