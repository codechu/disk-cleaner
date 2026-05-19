"""Thread-safe, multi-channel event bus — UI producers → API subscribers.

Events emitted in Disk Cleaner:

- ``scan.started``, ``scan.progress``, ``scan.finished``
- ``clean.started``, ``clean.finished``
- ``treemap.scan.started``, ``treemap.scan.finished``, ``treemap.drill``
- ``mount.changed``
- ``settings.changed``
- ``prefs.language.changed``, ``prefs.theme.changed`` (user-initiated)
- ``_keepalive`` (heartbeat, optional)

Design decisions:

- **Multi-channel**: ``event`` type is dot-separated (``scan.started``);
  subscribers filter via glob list (``["scan.*", "treemap.drill"]``).
  A "channel" is a glob set.
- **Thread-safe**: all public functions are lock-guarded; emit never
  blocks (each subscription has a bounded queue + ``put_nowait``).
- **Sync + async consumption**: :class:`Subscription` supports both
  ``for ev in sub:`` and ``async for ev in sub.aiter():``.
- **Context manager**: ``with subscribe([...]) as sub`` auto-calls
  ``unsubscribe`` (no leaks).
- **Resource limits**: ``MAX_SUBSCRIBERS`` (default 64) — exceeding
  raises :class:`SubscriberLimitExceeded`. Each queue is bounded by
  ``QUEUE_MAX`` (200); slow subscribers drop new events,
  ``sub.dropped`` counts; publisher never waits.
- **Stats**: :func:`stats` returns global counters + per-subscription
  details for monitoring / debug.
- **Heartbeat**: :class:`Subscription` with ``heartbeat=5.0`` emits
  ``_keepalive`` events on idle queues every N seconds (dead connection
  detection).
"""

from __future__ import annotations

import fnmatch
import queue
import threading
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import Any

#: Maximum events that can be held in a single subscription's queue.
QUEUE_MAX: int = 200

#: Maximum subscribers allowed concurrently (resource preservation).
MAX_SUBSCRIBERS: int = 64

#: Heartbeat interval (sec) when sync iter is idle. 0 = disabled.
DEFAULT_HEARTBEAT_SEC: float = 5.0


class SubscriberLimitExceeded(Exception):
    """``subscribe`` was called while MAX_SUBSCRIBERS was already reached."""


class Subscription:
    """Queue + filter + iter API for a single subscriber.

    Do not construct directly; use :func:`subscribe` or
    :func:`subscribe_ctx`.
    """

    __slots__ = (
        "types",
        "queue",
        "dropped",
        "received",
        "created_at",
        "heartbeat_sec",
        "_closed",
    )

    def __init__(self, types: list[str], heartbeat_sec: float) -> None:
        self.types: list[str] = list(types) if types else ["*"]
        self.queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=QUEUE_MAX)
        self.dropped: int = 0  # dropped due to backpressure
        self.received: int = 0  # successfully enqueued
        self.created_at: float = time.time()
        self.heartbeat_sec: float = heartbeat_sec
        self._closed: bool = False

    def matches(self, event_type: str) -> bool:
        """Does this subscription listen to this event type?"""
        return any(fnmatch.fnmatchcase(event_type, t) for t in self.types)

    def push(self, event: dict[str, Any]) -> None:
        """Called on the publisher side — non-blocking; drops if queue is full."""
        if self._closed:
            return
        try:
            self.queue.put_nowait(event)
            self.received += 1
        except queue.Full:
            self.dropped += 1

    def close(self) -> None:
        """Send a sentinel to terminate the iterator."""
        self._closed = True
        try:
            self.queue.put_nowait({"event": "_closed"})
        except queue.Full:
            pass  # consumer will see close after the next get

    # ---- Sync consumption ----

    def iter(
        self,
        *,
        timeout: float | None = None,
        heartbeat: bool = True,
    ) -> Iterator[dict[str, Any]]:
        """Yield events in order.

        If ``timeout`` is given and no event arrives within that period,
        iteration ends. If ``heartbeat=True`` and ``self.heartbeat_sec > 0``,
        a periodic ``_keepalive`` event is emitted on an empty queue (so the
        consumer can detect dead connections). If ``close()`` is called,
        iteration ends after the queue is drained.
        """
        deadline: float | None = None
        if timeout is not None:
            deadline = time.monotonic() + timeout

        hb_interval = self.heartbeat_sec if heartbeat and self.heartbeat_sec > 0 else None

        while True:
            # Effective get timeout: min of heartbeat and deadline
            get_timeout = hb_interval
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                get_timeout = min(get_timeout, remaining) if get_timeout else remaining
            try:
                event = self.queue.get(timeout=get_timeout)
            except queue.Empty:
                if hb_interval is not None:
                    yield {"event": "_keepalive", "ts": time.time()}
                    continue
                if deadline is not None:
                    return
                # Without heartbeat and deadline, block forever — we cannot
                # reach this branch (Empty cannot be raised with get_timeout=None).
                continue
            if event.get("event") == "_closed":
                return
            yield event

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return self.iter()

    # ---- Async consumption ----

    async def aiter(self, *, heartbeat: bool = True) -> AsyncIterator[dict[str, Any]]:
        """For asyncio callers: ``async for ev in sub.aiter(): ...``.

        The implementation uses ``loop.run_in_executor`` to wait for a
        blocking get on an executor thread — minimal asyncio integration
        with no extra dependency.
        """
        import asyncio

        loop = asyncio.get_event_loop()
        get_timeout = self.heartbeat_sec if heartbeat and self.heartbeat_sec > 0 else None
        while not self._closed:
            event = await loop.run_in_executor(None, _blocking_get, self.queue, get_timeout)
            if event is _EMPTY_SENTINEL:
                if heartbeat and self.heartbeat_sec > 0:
                    yield {"event": "_keepalive", "ts": time.time()}
                continue
            if event.get("event") == "_closed":
                return
            yield event


# ---- internal helpers ----

_EMPTY_SENTINEL: dict[str, Any] = {"__empty__": True}


def _blocking_get(
    q: queue.Queue[dict[str, Any]],
    timeout: float | None,
) -> dict[str, Any]:
    """Top-level function that needs to be picklable for ``run_in_executor``."""
    try:
        return q.get(timeout=timeout)
    except queue.Empty:
        return _EMPTY_SENTINEL


# ---- module globals ----

_lock = threading.Lock()
_subs: list[Subscription] = []
_total_emitted: int = 0


def subscribe(
    types: list[str] | None = None,
    *,
    heartbeat_sec: float = DEFAULT_HEARTBEAT_SEC,
) -> Subscription:
    """Create a new subscriber.

    Raises:
        SubscriberLimitExceeded: ``MAX_SUBSCRIBERS`` is already full.
    """
    with _lock:
        if len(_subs) >= MAX_SUBSCRIBERS:
            raise SubscriberLimitExceeded(
                f"max {MAX_SUBSCRIBERS} subscribers, current: {len(_subs)}"
            )
        sub = Subscription(types or ["*"], heartbeat_sec=heartbeat_sec)
        _subs.append(sub)
        return sub


def unsubscribe(sub: Subscription) -> None:
    """Remove the subscription (idempotent). Also calls ``sub.close()``."""
    with _lock:
        try:
            _subs.remove(sub)
        except ValueError:
            pass
    sub.close()


@contextmanager
def subscribe_ctx(
    types: list[str] | None = None,
    *,
    heartbeat_sec: float = DEFAULT_HEARTBEAT_SEC,
) -> Iterator[Subscription]:
    """``with subscribe_ctx([...]) as sub:`` — auto-unsubscribe on exit."""
    sub = subscribe(types, heartbeat_sec=heartbeat_sec)
    try:
        yield sub
    finally:
        unsubscribe(sub)


def emit(event_type: str, **fields: Any) -> None:
    """Publish a new event. The publisher never blocks.

    Args:
        event_type: Dot-separated type name (``scan.started``, ...).
            Names starting with ``_`` (``_keepalive``, ``_closed``) are
            reserved for internal use.
        **fields: Additional fields. ``event`` and ``ts`` are added
            automatically.
    """
    global _total_emitted
    event: dict[str, Any] = {
        "event": event_type,
        "ts": time.time(),
        **fields,
    }
    with _lock:
        targets = [s for s in _subs if s.matches(event_type)]
        _total_emitted += 1
    for s in targets:
        s.push(event)


def stats() -> dict[str, Any]:
    """Snapshot for monitoring: subscriber count, queue depth, drops."""
    with _lock:
        subs_info = [
            {
                "types": s.types,
                "queue_depth": s.queue.qsize(),
                "queue_max": QUEUE_MAX,
                "received": s.received,
                "dropped": s.dropped,
                "age_sec": round(time.time() - s.created_at, 1),
            }
            for s in _subs
        ]
        return {
            "subscribers": len(_subs),
            "max_subscribers": MAX_SUBSCRIBERS,
            "total_emitted": _total_emitted,
            "details": subs_info,
        }


def subscriber_count() -> int:
    """For test/debug: number of active subscribers."""
    with _lock:
        return len(_subs)


def reset_for_tests() -> None:
    """Tests only — close all subscriptions and reset counters."""
    global _total_emitted
    with _lock:
        for s in _subs:
            s.close()
        _subs.clear()
        _total_emitted = 0


__all__ = [
    "DEFAULT_HEARTBEAT_SEC",
    "MAX_SUBSCRIBERS",
    "QUEUE_MAX",
    "SubscriberLimitExceeded",
    "Subscription",
    "emit",
    "reset_for_tests",
    "stats",
    "subscribe",
    "subscribe_ctx",
    "subscriber_count",
    "unsubscribe",
]
