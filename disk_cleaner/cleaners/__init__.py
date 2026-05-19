"""Cleaner Strategy subpackage.

Three baseline implementations are provided: :class:`SafePathCleaner`
(single path), :class:`ContentsCleaner` (directory contents),
:class:`CommandCleaner` (shell/argv). To add a new cleanup type,
implement the :class:`Cleaner` ABC.
"""
from __future__ import annotations

from .base import Cleaner
from .command import CommandCleaner
from .contents import ContentsCleaner
from .safe_path import SafePathCleaner

__all__ = ["Cleaner", "CommandCleaner", "ContentsCleaner", "SafePathCleaner"]
