"""SettingsStore davranışı (geçici dizinde, üretim settings.json'a dokunma)."""
from __future__ import annotations

# Not: SettingsStore.load global SETTINGS_FILE yolundan okur; bu testler
# tam DI'a geçtikten sonra gerçek save/load akışını kontrol edecek.
# Şimdilik smoke: import + erişim.
from disk_cleaner.settings import SettingsStore


def test_settings_store_constructs(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    assert store.path.name == "settings.json"


def test_settings_store_load_returns_dict():
    store = SettingsStore()
    data = store.load()
    assert isinstance(data, dict)
