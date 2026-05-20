# SPDX-License-Identifier: GPL-3.0-or-later

"""Control API subpackage — JSON-line command server over a Unix socket."""

from __future__ import annotations

from .server import CONTROL_SOCKET, ControlServer

__all__ = ["CONTROL_SOCKET", "ControlServer"]
