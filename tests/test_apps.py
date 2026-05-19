"""``core.apps`` saf logic testleri."""
from __future__ import annotations

from disk_cleaner.core.apps import app_related_paths, list_installed_apps


def test_list_installed_apps_returns_list():
    pkgs = list_installed_apps(min_size_kb=10 * 1024)
    assert isinstance(pkgs, list)
    if pkgs:
        p = pkgs[0]
        assert {"name", "size", "desc"} <= set(p.keys())
        assert isinstance(p["size"], int)


def test_list_installed_apps_filters_libs():
    pkgs = list_installed_apps(min_size_kb=1)
    for p in pkgs:
        assert not p["name"].startswith("lib")
        assert not p["name"].startswith("linux-")
        assert not p["name"].startswith("python3-")


def test_list_installed_apps_sorted_descending():
    pkgs = list_installed_apps(min_size_kb=1024)
    if len(pkgs) >= 2:
        for a, b in zip(pkgs, pkgs[1:]):
            assert a["size"] >= b["size"]


def test_app_related_paths_returns_list_of_str(tmp_path, monkeypatch):
    paths = app_related_paths("definitely-not-installed-xyz")
    assert isinstance(paths, list)
    assert all(isinstance(p, str) for p in paths)


def test_app_related_paths_finds_known(monkeypatch, tmp_path):
    # Create a directory like ~/.config/foo and assert the function finds it
    fake_home = tmp_path
    config = fake_home / ".config" / "myapp"
    config.mkdir(parents=True)
    monkeypatch.setattr("disk_cleaner.core.apps.HOME", fake_home)
    paths = app_related_paths("myapp")
    assert str(config) in paths
