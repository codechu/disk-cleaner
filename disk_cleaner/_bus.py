"""Application-level event bus singleton.

``codechu-events`` 0.2 removed module-level shims (``events.emit``,
``events.subscribe``); callers construct their own :class:`Bus`. The
library principle forbids *library-level* singletons, but an
application-level one is appropriate: every controller, panel, and
control-socket subscriber in this product talks to the same bus.

Import this module from anywhere in the application::

    from disk_cleaner._bus import bus
    bus.emit("scan.started", panel="suggestion")
"""

from __future__ import annotations

from codechu_events import Bus

bus: Bus = Bus()

__all__ = ["bus"]
