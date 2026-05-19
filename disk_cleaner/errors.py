"""Disk Cleaner exception hierarchy.

Tüm domain hataları :class:`DiskCleanerError`'dan türetilir. Modüller kendi
spesifik hatalarını kullanır; çağıran kod tek bir base'i yakalayabilir.
"""
from __future__ import annotations


class DiskCleanerError(Exception):
    """Tüm disk-cleaner hatalarının ortak base'i."""


class ScannerError(DiskCleanerError):
    """Bir Scanner ``list_tasks`` çağrısı sırasında oluşan hata."""


class CleanerError(DiskCleanerError):
    """Bir Cleaner ``execute`` çağrısı sırasında oluşan hata."""


class StorageError(DiskCleanerError):
    """SQLite / ayar dosyası / snapshot katmanından gelen hata."""


class ApiError(DiskCleanerError):
    """Control API (Unix socket) işleyicisinde oluşan hata."""


class ConfigError(DiskCleanerError):
    """Geçersiz ayar veya kullanıcı tarafından sağlanan kural."""


__all__ = [
    "DiskCleanerError",
    "ScannerError",
    "CleanerError",
    "StorageError",
    "ApiError",
    "ConfigError",
]
