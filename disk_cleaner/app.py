"""Composition root — ``AppContext`` wires all dependencies together.

Public surface and DI point for new consumers. Consume Scanner /
Cleaner / Viz Strategy instances from here. UI and API can take
services directly off this object; the legacy callable factories still
live in :mod:`_tasks`.
"""

from __future__ import annotations

from pathlib import Path

from .config import HOME, SETTINGS_DIR
from .core.process import OpenPathsCache
from .scanners import (
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
    UserRulesScanner,
)
from .settings import SettingsStore
from .storage.du_cache import DuCache
from .storage.snapshots import SnapshotStore


class AppContext:
    """Composition root where services come together in one place.

    To add a new service: add it in the constructor, write a type hint,
    and keep naming consistency character by character.
    """

    def __init__(
        self,
        settings_dir: Path | None = None,
        workspace_root: str | Path | None = None,
        downloads_root: str | Path | None = None,
        old_files_days: int = 90,
    ) -> None:
        self.settings_dir: Path = Path(settings_dir or SETTINGS_DIR)
        self.settings_dir.mkdir(parents=True, exist_ok=True)

        self.settings: SettingsStore = SettingsStore(self.settings_dir / "settings.json")
        self.du_cache: DuCache = DuCache(self.settings_dir / "du_cache.db")
        self.snapshots: SnapshotStore = SnapshotStore(self.settings_dir / "snapshots.db")
        self.open_paths: OpenPathsCache = OpenPathsCache()

        ws = workspace_root or self.settings.get("workspace", HOME / "workspace")
        dl = downloads_root or self.settings.get("downloads", HOME / "Downloads")

        self.scanners: ScannerRegistry = ScannerRegistry()
        self.scanners.register("system", SystemScanner())
        self.scanners.register("artifacts", ArtifactScanner(ws))
        self.scanners.register("explorer", ExplorerScanner(ws))
        self.scanners.register("old_files", OldFilesScanner(dl, days=old_files_days))
        self.scanners.register("duplicates", DuplicatesScanner(ws))
        self.scanners.register("empty", EmptyScanner(ws))
        self.scanners.register("similar", SimilarImagesScanner(HOME / "Pictures"))
        self.scanners.register("apps", AppUninstallScanner())
        self.scanners.register("user_rules", UserRulesScanner())

    def scanner(self, name: str) -> Scanner:
        return self.scanners.get(name)


__all__ = ["AppContext"]
