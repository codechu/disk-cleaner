"""Açık dosya / süreç farkındalığı (``lsof`` cache).

Skorlayıcı, "bu yol şu an açık mı?" sorusunu çağırma başına lsof
spawn etmeden cevaplayabilsin diye düşük-frekanslı bir cache kullanır.
"""
from __future__ import annotations

import os
import time

from ..utils import run

_DEFAULT_MAX_AGE = 30.0

# Module-level cache — tüm get_open_paths çağrıları paylaşır.
_OPEN_PATHS_CACHE: dict[str, object] = {"ts": 0.0, "paths": set()}


def get_open_paths(max_age: float = _DEFAULT_MAX_AGE) -> set[tuple[str, str]]:
    """lsof ile bu kullanıcının açık tuttuğu ``(path, cmd)`` çiftlerini döndür.

    Cache TTL ``max_age`` sn. Hata durumunda boş set döner.
    """
    now = time.monotonic()
    ts = _OPEN_PATHS_CACHE["ts"]
    if isinstance(ts, float) and now - ts < max_age:
        cached = _OPEN_PATHS_CACHE["paths"]
        if isinstance(cached, set):
            return cached
    paths: set[tuple[str, str]] = set()
    rc, out = run(["lsof", "-F", "nc", "-u", str(os.getuid())], timeout=15)
    if rc == 0:
        current_cmd = ""
        for line in out.splitlines():
            if not line:
                continue
            tag, val = line[0], line[1:]
            if tag == "c":
                current_cmd = val
            elif tag == "n" and val.startswith("/"):
                paths.add((val, current_cmd))
    _OPEN_PATHS_CACHE["ts"] = now
    _OPEN_PATHS_CACHE["paths"] = paths
    return paths


def path_holders(path: str, open_paths: set[tuple[str, str]]) -> set[str]:
    """``path`` (veya altındaki bir yol) açık tutan süreç adlarını döndür."""
    if not path:
        return set()
    p = os.path.abspath(os.path.expanduser(path)).rstrip("/")
    holders: set[str] = set()
    for op, cmd in open_paths:
        if op == p or op.startswith(p + "/"):
            holders.add(cmd)
    return holders


class OpenPathsCache:
    """``get_open_paths`` üstüne ince OOP sarmalayıcı (DI için)."""

    def __init__(self, max_age: float = _DEFAULT_MAX_AGE) -> None:
        self.max_age = max_age

    def snapshot(self) -> set[tuple[str, str]]:
        return get_open_paths(max_age=self.max_age)

    def holders(self, path: str) -> set[str]:
        return path_holders(path, self.snapshot())


__all__ = ["OpenPathsCache", "get_open_paths", "path_holders"]
