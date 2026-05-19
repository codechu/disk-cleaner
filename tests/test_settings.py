"""SettingsStore behavior (in a temp dir, don't touch production settings.json)."""

from __future__ import annotations

# Note: SettingsStore.load reads from the global SETTINGS_FILE path; these
# tests will exercise the real save/load flow once full DI lands. For
# now, smoke test only: import + access.
from disk_cleaner.settings import SettingsStore


def test_settings_store_constructs(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    assert store.path.name == "settings.json"


def test_settings_store_load_returns_dict():
    store = SettingsStore()
    data = store.load()
    assert isinstance(data, dict)
