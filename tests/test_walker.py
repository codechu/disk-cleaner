# SPDX-License-Identifier: GPL-3.0-or-later

"""Pure-logic tests for ``core.walker`` (using tmp_path)."""

from __future__ import annotations

import os
import time

from disk_cleaner.core.walker import (
    ARTIFACT_DIRS,
    ARTIFACT_RISK,
    find_duplicates,
    find_empty_items,
    find_git_root,
    find_old_files,
    find_project_artifacts,
    list_dir_children,
    project_activity_days,
)


def test_artifact_constants_consistent():
    # The risk map must be a subset of ARTIFACT_DIRS.
    for d in ARTIFACT_RISK:
        assert d in ARTIFACT_DIRS


def test_find_project_artifacts_finds_node_modules(tmp_path):
    nm = tmp_path / "proj" / "node_modules"
    nm.mkdir(parents=True)
    (nm / "x.js").write_text("")
    found = find_project_artifacts(tmp_path)
    assert any(p.endswith("node_modules") for p in found)


def test_find_project_artifacts_does_not_descend_into_artifact(tmp_path):
    inner = tmp_path / "proj" / "node_modules" / "sub" / "dist"
    inner.mkdir(parents=True)
    found = find_project_artifacts(tmp_path)
    # node_modules must be found; the nested dist must not be reported
    assert any(p.endswith("node_modules") for p in found)
    assert not any(p.endswith("/dist") for p in found)


def test_find_git_root(tmp_path):
    (tmp_path / "proj" / ".git").mkdir(parents=True)
    deep = tmp_path / "proj" / "src" / "lib"
    deep.mkdir(parents=True)
    root = find_git_root(deep / "file.py")
    assert root == tmp_path / "proj"


def test_find_git_root_no_git_returns_none(tmp_path):
    assert find_git_root(tmp_path / "x.txt") is None


def test_project_activity_days_uses_head(tmp_path):
    git = tmp_path / "proj" / ".git"
    git.mkdir(parents=True)
    head = git / "HEAD"
    head.write_text("ref: refs/heads/main")
    old = time.time() - 10 * 86400
    os.utime(head, (old, old))
    days = project_activity_days(tmp_path / "proj" / "anything")
    assert days is not None
    assert 9.5 < days < 10.5


def test_list_dir_children(tmp_path):
    (tmp_path / "a").write_text("")
    (tmp_path / "b").mkdir()
    children = list_dir_children(tmp_path)
    assert len(children) == 2


def test_find_old_files(tmp_path):
    f = tmp_path / "old.txt"
    f.write_text("x" * 100)
    long_ago = time.time() - 100 * 86400
    os.utime(f, (long_ago, long_ago))
    new = tmp_path / "new.txt"
    new.write_text("y")
    items = find_old_files(tmp_path, days=30)
    paths = [p for p, _, _ in items]
    assert str(f) in paths
    assert str(new) not in paths


def test_find_empty_items(tmp_path):
    (tmp_path / "empty_dir").mkdir()
    (tmp_path / "zero.txt").write_text("")
    (tmp_path / "nonzero.txt").write_text("x")
    empty_dirs, zeros = find_empty_items(tmp_path)
    assert any(p.endswith("empty_dir") for p in empty_dirs)
    assert any(p.endswith("zero.txt") for p in zeros)
    assert not any(p.endswith("nonzero.txt") for p in zeros)


def test_find_duplicates_groups_identical(tmp_path):
    content = b"x" * (2 * 1024 * 1024)
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(content)
    b.write_bytes(content)
    (tmp_path / "c.bin").write_bytes(b"y" * (2 * 1024 * 1024))
    groups = find_duplicates(tmp_path, min_size=1024 * 1024)
    # At least one group, and a and b must be in that group
    assert any(set(group) >= {str(a), str(b)} for _, group in groups)
