# SPDX-License-Identifier: GPL-3.0-or-later

"""Disk Cleaner exception hierarchy.

All domain errors derive from :class:`DiskCleanerError`. Modules use
their own specific errors; calling code can catch the single base.
"""

from __future__ import annotations


class DiskCleanerError(Exception):
    """Common base for all disk-cleaner errors."""


class ScannerError(DiskCleanerError):
    """Error raised during a Scanner ``list_tasks`` call."""


class CleanerError(DiskCleanerError):
    """Error raised during a Cleaner ``execute`` call."""


class StorageError(DiskCleanerError):
    """Error from the SQLite / settings file / snapshot layer."""


class ApiError(DiskCleanerError):
    """Error raised inside the Control API (Unix socket) handler."""


class ConfigError(DiskCleanerError):
    """Invalid setting or user-supplied rule."""


__all__ = [
    "DiskCleanerError",
    "ScannerError",
    "CleanerError",
    "StorageError",
    "ApiError",
    "ConfigError",
]
