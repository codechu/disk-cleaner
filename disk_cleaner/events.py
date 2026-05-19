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
from contextlib import contextmanager
from typing import Any, AsyncIterator, Iterator

#: Tek subscription'ın kuyruğunda tutulabilen maks olay.
QUEUE_MAX: int = 200

#: Aynı anda izin verilen maks abone (kaynak korunumu).
MAX_SUBSCRIBERS: int = 64

#: Sync iter idle olduğunda heartbeat aralığı (sn). 0 = kapalı.
DEFAULT_HEARTBEAT_SEC: float = 5.0


class SubscriberLimitExceeded(Exception):
    """``subscribe`` çağrısı MAX_SUBSCRIBERS aşılırken yapıldı."""


class Subscription:
    """Tek subscriber için kuyruk + filtre + iter API.

    Doğrudan oluşturmayın; :func:`subscribe` veya
    :func:`subscribe_ctx` kullanın.
    """

    __slots__ = (
        "types", "queue", "dropped", "received",
        "created_at", "heartbeat_sec", "_closed",
    )

    def __init__(self, types: list[str], heartbeat_sec: float) -> None:
        self.types: list[str] = list(types) if types else ["*"]
        self.queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=QUEUE_MAX)
        self.dropped: int = 0  # backpressure ile düşürülen
        self.received: int = 0  # kuyruğa başarıyla giren
        self.created_at: float = time.time()
        self.heartbeat_sec: float = heartbeat_sec
        self._closed: bool = False

    def matches(self, event_type: str) -> bool:
        """Bu olay tipini bu subscription dinliyor mu?"""
        return any(fnmatch.fnmatchcase(event_type, t) for t in self.types)

    def push(self, event: dict[str, Any]) -> None:
        """Yayıncı tarafında çağrılır — non-blocking, kapasite dolu ise düşür."""
        if self._closed:
            return
        try:
            self.queue.put_nowait(event)
            self.received += 1
        except queue.Full:
            self.dropped += 1

    def close(self) -> None:
        """İter'i sonlandırmak için sentinel gönder."""
        self._closed = True
        try:
            self.queue.put_nowait({"event": "_closed"})
        except queue.Full:
            pass  # consumer get'ten sonra zaten close görecek

    # ---- Sync tüketim ----

    def iter(
        self,
        *,
        timeout: float | None = None,
        heartbeat: bool = True,
    ) -> Iterator[dict[str, Any]]:
        """Olayları sıralı döndür.

        ``timeout`` verilirse o kadar süre içinde event gelmezse iter biter.
        ``heartbeat=True`` ve ``self.heartbeat_sec > 0`` ise boş kuyrukta
        periyodik ``_keepalive`` event'i üretilir (consumer dead-detect
        edebilsin). ``close()`` çağrılırsa kuyruk drain edildikten sonra
        iter biter.
        """
        deadline: float | None = None
        if timeout is not None:
            deadline = time.monotonic() + timeout

        hb_interval = (
            self.heartbeat_sec if heartbeat and self.heartbeat_sec > 0 else None
        )

        while True:
            # Etkili get timeout: heartbeat ve deadline'ın min'i
            get_timeout = hb_interval
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                get_timeout = (
                    min(get_timeout, remaining) if get_timeout else remaining
                )
            try:
                event = self.queue.get(timeout=get_timeout)
            except queue.Empty:
                if hb_interval is not None:
                    yield {"event": "_keepalive", "ts": time.time()}
                    continue
                if deadline is not None:
                    return
                # heartbeat ve deadline yoksa sonsuza dek bekle — bu kola
                # düşemeyiz (get_timeout=None ile Empty olmaz).
                continue
            if event.get("event") == "_closed":
                return
            yield event

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return self.iter()

    # ---- Async tüketim ----

    async def aiter(self, *, heartbeat: bool = True) -> AsyncIterator[dict[str, Any]]:
        """asyncio caller'lar için: ``async for ev in sub.aiter(): ...``.

        Implementasyon ``loop.run_in_executor`` ile blocking get'i bir
        executor thread'inde bekler — minimal asyncio entegrasyonu, ekstra
        bağımlılık yok.
        """
        import asyncio

        loop = asyncio.get_event_loop()
        get_timeout = self.heartbeat_sec if heartbeat and self.heartbeat_sec > 0 else None
        while not self._closed:
            event = await loop.run_in_executor(
                None, _blocking_get, self.queue, get_timeout
            )
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
    """``run_in_executor`` için pickle'lanması gereken üst-seviye fonksiyon."""
    try:
        return q.get(timeout=timeout)
    except queue.Empty:
        return _EMPTY_SENTINEL


# ---- modül global'leri ----

_lock = threading.Lock()
_subs: list[Subscription] = []
_total_emitted: int = 0


def subscribe(
    types: list[str] | None = None,
    *,
    heartbeat_sec: float = DEFAULT_HEARTBEAT_SEC,
) -> Subscription:
    """Yeni abone oluştur.

    Raises:
        SubscriberLimitExceeded: ``MAX_SUBSCRIBERS`` zaten dolu.
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
    """Aboneliği kaldır (idempotent). ``sub.close()`` da çağırır."""
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
    """``with subscribe_ctx([...]) as sub:`` — kapanışta otomatik unsubscribe."""
    sub = subscribe(types, heartbeat_sec=heartbeat_sec)
    try:
        yield sub
    finally:
        unsubscribe(sub)


def emit(event_type: str, **fields: Any) -> None:
    """Yeni bir olay yayınla. Yayıncı hiç bloke olmaz.

    Args:
        event_type: Nokta-ayrımlı tip adı (``scan.started``, ...).
            ``_`` ile başlayan adlar (``_keepalive``, ``_closed``) iç
            kullanım için ayrılmış.
        **fields: Ek alanlar. ``event`` ve ``ts`` otomatik eklenir.
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
    """Monitoring için anlık durum: subscriber sayısı, queue derinliği, drop."""
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
    """Test/debug için: aktif subscriber sayısı."""
    with _lock:
        return len(_subs)


def reset_for_tests() -> None:
    """Yalnızca testlerde — tüm subscription'ları kapat ve sayaçları sıfırla."""
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
