# SPDX-License-Identifier: GPL-3.0-or-later

"""Cleaner Strategy base class.

A :class:`Cleaner` performs the cleanup operation via ``execute()``.
Destructive operations go **to trash by default**; permanent deletion
happens only when the user requests it explicitly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Cleaner(ABC):
    """A cleanup strategy.

    Implementations: :class:`SafePathCleaner`, :class:`ContentsCleaner`,
    :class:`CommandCleaner`, :class:`AptPurgeCleaner`,
    :class:`SnapCleaner`. All return (returncode, message) — the UI
    shows the summary; the log keeps the detail.
    """

    @abstractmethod
    def execute(self) -> tuple[int, str]:
        """Returns ``(returncode, message)``.

        ``returncode == 0`` means success; anything else is an error.
        ``message`` is a short, user-displayable text.
        """


__all__ = ["Cleaner"]
