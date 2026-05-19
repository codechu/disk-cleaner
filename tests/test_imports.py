"""Public API import smoke tests.

Quickly catch what a refactor breaks whenever the package structure changes.
"""
from __future__ import annotations


def test_package_version():
    import disk_cleaner

    assert isinstance(disk_cleaner.__version__, str)


def test_public_top_level_imports():
    from disk_cleaner import app, cli, config, errors, settings, theme, utils  # noqa: F401


def test_public_subpackage_imports():
    from disk_cleaner.cleaners import Cleaner  # noqa: F401
    from disk_cleaner.core import compute_score_and_reason, dir_size  # noqa: F401
    from disk_cleaner.scanners import Scanner, ScannerRegistry, Task  # noqa: F401
    from disk_cleaner.storage import DuCache, SnapshotStore  # noqa: F401
    from disk_cleaner.viz import TreeNode, VizStrategy  # noqa: F401


def test_errors_hierarchy():
    from disk_cleaner.errors import (
        ApiError,
        CleanerError,
        ConfigError,
        DiskCleanerError,
        ScannerError,
        StorageError,
    )

    for cls in (ScannerError, CleanerError, StorageError, ApiError, ConfigError):
        assert issubclass(cls, DiskCleanerError)
