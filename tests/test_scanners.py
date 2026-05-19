"""Scanner sınıfları smoke testleri (Strategy yüzeyini doğrular)."""
from __future__ import annotations

from disk_cleaner.app import AppContext
from disk_cleaner.cleaners.base import Cleaner
from disk_cleaner.scanners import (
    AppUninstallScanner,
    ArtifactScanner,
    DuplicatesScanner,
    EmptyScanner,
    ExplorerScanner,
    OldFilesScanner,
    Scanner,
    ScannerRegistry,
    SimilarImagesScanner,
    SystemScanner,
    Task,
    UserRulesScanner,
)

ALL_SCANNERS = (
    SystemScanner,
    ArtifactScanner,
    ExplorerScanner,
    OldFilesScanner,
    DuplicatesScanner,
    EmptyScanner,
    SimilarImagesScanner,
    AppUninstallScanner,
    UserRulesScanner,
)


def test_scanners_implement_abc():
    for cls in ALL_SCANNERS:
        assert issubclass(cls, Scanner)


def test_scanner_registry():
    r = ScannerRegistry()
    s = SystemScanner()
    r.register("system", s)
    assert "system" in r
    assert r.get("system") is s
    assert list(r)[0] == ("system", s)


def test_system_scanner_yields_tasks():
    scanner = SystemScanner()
    tasks = list(scanner.list_tasks())
    assert len(tasks) > 0
    for t in tasks:
        assert isinstance(t, Task)
        assert isinstance(t.cleaner, Cleaner)
        assert t.kind == "system"
        assert t.risk in ("low", "medium", "high")


def test_appcontext_wires_all_scanners(tmp_path):
    ctx = AppContext(settings_dir=tmp_path)
    expected = {
        "system", "artifacts", "explorer", "old_files", "duplicates",
        "empty", "similar", "apps", "user_rules",
    }
    actual = {name for name, _ in ctx.scanners}
    assert actual == expected


def test_appcontext_scanner_lookup(tmp_path):
    ctx = AppContext(settings_dir=tmp_path)
    s = ctx.scanner("system")
    assert isinstance(s, SystemScanner)
