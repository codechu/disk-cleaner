"""Core domain — UI-bağımsız, test edilebilir saf mantık.

Submodüller: ``sizing``, ``safe_remove``, ``process``, ``score``,
``kernels``, ``walker``, ``system_helpers``, ``apps``. Public yüzey
``__all__`` üzerinden sabit.
"""
from __future__ import annotations

from .apps import app_related_paths, list_installed_apps
from .kernels import (
    _list_kernel_pkgs,
    _old_kernel_pkgs,
    clean_old_kernels,
    list_installed_kernels,
    list_old_kernels,
    size_old_kernels,
)
from .process import OpenPathsCache, get_open_paths, path_holders
from .safe_remove import rm_contents, rm_path, safe_remove
from .score import compute_score_and_reason
from .sizing import apparent_size, dir_size, is_sparse, path_size
from .system_helpers import (
    _clean_multi,
    _firefox_profile_dirs,
    clean_cache_except_chrome,
    clean_firefox_cache,
    clean_snap_disabled_action,
    size_apt,
    size_docker_builder,
    size_docker_dangling_images,
    size_docker_stopped_containers,
    size_firefox_cache,
    size_flatpak_unused,
    size_journal,
    size_snap_disabled,
)
from .walker import (
    ARTIFACT_DIRS,
    ARTIFACT_RISK,
    find_duplicates,
    find_empty_items,
    find_git_root,
    find_old_files,
    find_project_artifacts,
    find_similar_images,
    list_dir_children,
    project_activity_days,
)

__all__ = [
    "ARTIFACT_DIRS",
    "ARTIFACT_RISK",
    "OpenPathsCache",
    "app_related_paths",
    "apparent_size",
    "clean_cache_except_chrome",
    "clean_firefox_cache",
    "clean_old_kernels",
    "clean_snap_disabled_action",
    "compute_score_and_reason",
    "dir_size",
    "find_duplicates",
    "find_empty_items",
    "find_git_root",
    "find_old_files",
    "find_project_artifacts",
    "find_similar_images",
    "get_open_paths",
    "is_sparse",
    "list_dir_children",
    "list_installed_apps",
    "list_installed_kernels",
    "list_old_kernels",
    "path_holders",
    "path_size",
    "rm_contents",
    "rm_path",
    "safe_remove",
    "size_apt",
    "size_docker_builder",
    "size_docker_dangling_images",
    "size_docker_stopped_containers",
    "size_firefox_cache",
    "size_flatpak_unused",
    "size_journal",
    "size_old_kernels",
    "size_snap_disabled",
]
