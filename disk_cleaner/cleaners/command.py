"""CommandCleaner — bir shell/argv komutu çalıştır.

``need_root=True`` ise ``pkexec`` ile sarmalanır. ``DRY_RUN`` çağrı
anında :mod:`disk_cleaner.runtime`'den okunur (runtime mutable).
"""
from __future__ import annotations

import os
import subprocess

from ..i18n import _
from ..utils import run
from .base import Cleaner


class CommandCleaner(Cleaner):
    """Argv listesi veya shell string komutunu çalıştır."""

    def __init__(
        self,
        cmd: list[str] | str,
        shell: bool = False,
        need_root: bool = False,
    ) -> None:
        self.cmd = cmd
        self.shell = shell
        self.need_root = need_root

    def execute(self) -> tuple[int, str]:
        from .. import runtime

        if runtime.DRY_RUN:
            display = self.cmd if isinstance(self.cmd, str) else " ".join(self.cmd)
            return 0, _("[DRY] would have run: {display}").format(display=display)
        c: list[str] | str = self.cmd
        if self.need_root and os.geteuid() != 0:
            if isinstance(c, list):
                c = ["pkexec", *c]
            else:
                c = "pkexec sh -c " + subprocess.list2cmdline([c])
        return run(c, shell=self.shell)


__all__ = ["CommandCleaner"]
