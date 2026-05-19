"""SuggestionController — akıllı tarama state machine'i.

Toplam tüm tarayıcıları (sistem cache + proje artefaktları + eski
dosyalar) arka planda çalıştırır, ``compute_score_and_reason`` ile
skorlar, snapshot kaydeder + 7-gün büyüme analizi yapar, sonuçları
hiyerarşik olarak gruplayıp (📦 ``node_modules`` gibi artefakt türleri)
sıralı şekilde sunar. Muhafazakar auto-select: top-N + skor eşiği +
kümülatif boyut tavanı.

View'ın görevi (TreeStore, filtre, sort, dialog, right-click menu) bu
sınıfta yok.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .. import events
from ..config import HOME
from ..i18n import _, ngettext
from ..core.process import get_open_paths
from ..core.score import compute_score_and_reason
from ..settings import add_to_blacklist, is_blacklisted
from ..storage.snapshots import compute_growth, save_snapshot
from ..utils import ThrottledProgress, human


@dataclass
class SuggestionRow:
    """Hiyerarşik öneri satırı — grup veya yaprak task."""

    tid: int                       # -1: grup; >=0: task id
    name: str
    score: int                     # 0..100+
    size_bytes: int
    size_text: str
    reason: str
    risk_color: str                # hex
    kind: str                      # "system" / "artifact" / "oldfile" / "group"
    is_group: bool
    checked: bool = False
    status_marker: str = ""        # "✓ " / "✗ " temizlik sonrası
    children: list["SuggestionRow"] = field(default_factory=list)


@dataclass
class GrowthItem:
    path: str
    name: str
    current_size: int
    prev_size: int
    delta: int
    ratio: float


@dataclass
class GrowthInfo:
    prev_scanned_at: float
    items: list[GrowthItem]


@dataclass
class CleanPreview:
    count: int
    total_bytes: int
    items: list[tuple[int, int, str]]   # (group_idx, child_idx, name)


@dataclass
class ExportRow:
    name: str
    path: str
    kind: str
    size_bytes: int
    size_human: str
    score: int
    reason: str
    risk: str
    selected: bool


# Muhafazakar auto-select sabitleri
AUTO_SELECT_TOP_N = 5
AUTO_SELECT_MAX_GB = 5.0
AUTO_SELECT_MIN_SCORE = 60

# Boyut filtresi — bu eşiğin altındaki görevler gösterilmez
MIN_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

# Onay diyalogu için maks öğe göstergesi
MAX_PREVIEW_ITEMS = 15


class SuggestionController:
    """Akıllı tarama state machine'i — View-bağımsız."""

    def __init__(self) -> None:
        # State
        self.rows: list[SuggestionRow] = []
        self.tasks: dict[int, dict[str, Any]] = {}
        self._next_tid = 0
        self._cancel_event = threading.Event()
        self._busy = False
        self.last_growth: GrowthInfo | None = None

        # Observers
        self.on_busy_changed: Callable[[bool, str], None] = _noop2
        self.on_rows_replaced: Callable[[list[SuggestionRow], GrowthInfo | None], None] = _noop2
        self.on_row_updated: Callable[[int, int, SuggestionRow], None] = _noop3   # (group_idx, child_idx, row)
        self.on_total_changed: Callable[[int, int], None] = _noop2  # (count, total_bytes)
        self.on_progress: Callable[[str], None] = _noop
        self.on_log: Callable[[str], None] = _noop
        self.on_disk_label_dirty: Callable[[], None] = _noop
        self.on_row_removed: Callable[[int, int], None] = _noop2

    # ---- Public commands ----

    def start_scan(self) -> None:
        if self._busy:
            return
        self._cancel_event.clear()
        self.rows = []
        self.tasks = {}
        self._next_tid = 0
        self._set_busy(True, _("Detecting open files…"))
        self.on_log("\n--- " + _("Smart scan started") + " ---\n")
        events.emit("scan.started", panel="suggestion")
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def cancel(self) -> None:
        self._cancel_event.set()
        self.on_progress(_("Cancelling…"))

    def toggle(self, group_idx: int, child_idx: int | None) -> None:
        """child_idx None ise grubun kendisi toggle edilir; alt çocuklar
        aynı duruma getirilir."""
        if not (0 <= group_idx < len(self.rows)):
            return
        row = self.rows[group_idx]
        if child_idx is None:
            new_val = not row.checked
            row.checked = new_val
            self.on_row_updated(group_idx, -1, row)
            if row.is_group:
                for ci, child in enumerate(row.children):
                    child.checked = new_val
                    self.on_row_updated(group_idx, ci, child)
        else:
            if not (0 <= child_idx < len(row.children)):
                return
            child = row.children[child_idx]
            child.checked = not child.checked
            self.on_row_updated(group_idx, child_idx, child)
        self._emit_total()

    def select_all(self) -> None:
        self._set_all(True)

    def select_none(self) -> None:
        self._set_all(False)

    def select_target(self, target_bytes: int) -> int:
        """Düşük riskli + skor sırasıyla kümülatif boyut hedefini aşana
        kadar seç. Önceki seçim sıfırlanır. Returns: seçilen sayısı.
        """
        self._set_all(False)
        # Yaprakları topla — düşük risk
        from .. import settings  # avoid top-level circular
        leaves: list[tuple[int, int, int, int]] = []  # (gidx, cidx, score, size)
        for gi, row in enumerate(self.rows):
            if row.is_group:
                for ci, child in enumerate(row.children):
                    if child.risk_color == _LOW_COLOR:
                        leaves.append((gi, ci, child.score, child.size_bytes))
            elif row.risk_color == _LOW_COLOR:
                leaves.append((gi, -1, row.score, row.size_bytes))
        leaves.sort(key=lambda x: -x[2])
        cumulative = 0
        picked = 0
        for gi, ci, _sc, size in leaves:
            if cumulative >= target_bytes:
                break
            if ci == -1:
                self.rows[gi].checked = True
                self.on_row_updated(gi, -1, self.rows[gi])
            else:
                child = self.rows[gi].children[ci]
                child.checked = True
                self.on_row_updated(gi, ci, child)
            cumulative += size
            picked += 1
        self._emit_total()
        self.on_log(
            _(
                "Targeted selection: {picked} items, {total} (target: {target})"
            ).format(
                picked=picked,
                total=human(cumulative),
                target=human(target_bytes),
            )
            + "\n"
        )
        return picked

    def start_clean(self, confirm: Callable[[CleanPreview], bool]) -> bool:
        """Confirm callback senkron çağrılır. Returns: başlatıldıysa True."""
        selected: list[tuple[int, int, dict[str, Any]]] = []
        for gi, row in enumerate(self.rows):
            if row.is_group:
                for ci, child in enumerate(row.children):
                    if child.checked and child.tid >= 0:
                        task = self.tasks.get(child.tid)
                        if task:
                            selected.append((gi, ci, task))
            elif row.checked and row.tid >= 0:
                task = self.tasks.get(row.tid)
                if task:
                    selected.append((gi, -1, task))
        if not selected:
            return False
        total = sum(
            (self.rows[gi].children[ci].size_bytes if ci >= 0 else self.rows[gi].size_bytes)
            for gi, ci, _ in selected
        )
        preview = CleanPreview(
            count=len(selected),
            total_bytes=total,
            items=[
                (gi, ci, t["name"]) for gi, ci, t in selected[:MAX_PREVIEW_ITEMS]
            ],
        )
        if not confirm(preview):
            return False
        self._cancel_event.clear()
        self._set_busy(True, f"0 / {len(selected)}")
        events.emit("clean.started", panel="suggestion", count=len(selected))
        threading.Thread(
            target=self._clean_thread, args=(selected,), daemon=True
        ).start()
        return True

    def blacklist_and_remove(self, group_idx: int, child_idx: int | None) -> None:
        """Bir yolu blacklist'e ekle ve satırı kaldır."""
        if not (0 <= group_idx < len(self.rows)):
            return
        if child_idx is None or child_idx < 0:
            row = self.rows[group_idx]
        else:
            row = self.rows[group_idx].children[child_idx]
        task = self.tasks.get(row.tid)
        if not task:
            return
        path = task.get("path", "")
        add_to_blacklist(path)
        # Satırı kaldır
        if child_idx is None or child_idx < 0:
            del self.rows[group_idx]
            self.on_row_removed(group_idx, -1)
        else:
            del self.rows[group_idx].children[child_idx]
            self.on_row_removed(group_idx, child_idx)
        self.on_log(_("🚫 Added to blacklist: {path}").format(path=path) + "\n")
        self._emit_total()

    def export_rows(self) -> list[ExportRow]:
        """Mevcut tüm öğeleri (grup hariç) dışa aktarma için düz liste."""
        out: list[ExportRow] = []
        for row in self.rows:
            if row.is_group:
                for child in row.children:
                    out.append(self._export_row(child))
            else:
                out.append(self._export_row(row))
        return out

    def _export_row(self, row: SuggestionRow) -> ExportRow:
        task = self.tasks.get(row.tid, {})
        return ExportRow(
            name=row.name,
            path=task.get("path", ""),
            kind=row.kind,
            size_bytes=row.size_bytes,
            size_human=row.size_text,
            score=row.score,
            reason=row.reason,
            risk=task.get("risk", ""),
            selected=row.checked,
        )

    # ---- Properties ----

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def total_bytes(self) -> int:
        total = 0
        for row in self.rows:
            if row.is_group:
                total += sum(c.size_bytes for c in row.children if c.checked)
            elif row.checked:
                total += row.size_bytes
        return total

    @property
    def selected_count(self) -> int:
        n = 0
        for row in self.rows:
            if row.is_group:
                n += sum(1 for c in row.children if c.checked)
            elif row.checked:
                n += 1
        return n

    @property
    def total_items(self) -> int:
        """Yaprak sayısı (grup değil)."""
        n = 0
        for row in self.rows:
            if row.is_group:
                n += len(row.children)
            else:
                n += 1
        return n

    # ---- Internals — scan ----

    def _scan_thread(self) -> None:
        from .. import _tasks

        progress = ThrottledProgress(self.on_progress)

        open_paths = get_open_paths()
        if self._cancel_event.is_set():
            self._set_busy(False, _("Cancelled"))
            return

        enriched = self._gather_enriched(_tasks, progress, open_paths)

        # Snapshot + growth
        items_for_db = [
            {
                "path": t.get("path", ""), "kind": kind,
                "size_bytes": size, "score": int(score),
                "risk": t.get("risk", ""), "name": t.get("name", ""),
            }
            for t, size, kind, score, _ in enriched
        ]
        try:
            save_snapshot(items_for_db, mount="/")
        except Exception:
            pass
        try:
            raw_growth = compute_growth(items_for_db, mount="/", days_back=7)
        except Exception:
            raw_growth = None
        growth_info = _coerce_growth(raw_growth)
        self.last_growth = growth_info

        # Gruplama
        groups, singles = _group_enriched(enriched)

        # Auto-select kararı (score sırasıyla, kümülatif cap)
        auto_set: set[int] = _compute_auto_select(groups, singles)

        # Hiyerarşik satır yapısı kur
        self.rows = self._build_rows(groups, singles, auto_set)

        self.on_rows_replaced(self.rows, growth_info)
        self._set_busy(False, "")
        group_count = sum(1 for r in self.rows if r.is_group)
        suggestions_msg = ngettext(
            "{n} suggestion", "{n} suggestions", self.total_items
        ).format(n=self.total_items)
        groups_msg = ngettext(
            "{n} group", "{n} groups", group_count
        ).format(n=group_count)
        self.on_log(
            _("Smart scan complete: {suggestions} ({groups})").format(
                suggestions=suggestions_msg, groups=groups_msg,
            )
            + "\n"
        )
        events.emit(
            "scan.finished",
            panel="suggestion",
            count=self.total_items,
            groups=sum(1 for r in self.rows if r.is_group),
        )

    def _gather_enriched(
        self,
        _tasks_mod,
        progress: Callable[[str], None],
        open_paths,
    ) -> list[tuple[dict[str, Any], int, str, float, str]]:
        results: list[tuple[dict[str, Any], int, str]] = []

        # Sistem cache
        progress(_("Scanning system caches…"))
        for t in _tasks_mod.SYSTEM_TASKS:
            if self._cancel_event.is_set():
                break
            try:
                size = t["size_fn"]() or 0
            except Exception:
                size = 0
            if size >= MIN_SIZE_BYTES:
                results.append((t, size, "system"))

        # Proje artefaktları
        ws = HOME / "workspace"
        if ws.exists() and not self._cancel_event.is_set():
            progress(_("Searching for project artifacts…"))
            try:
                art_tasks = _tasks_mod.make_artifact_tasks(
                    str(ws), cancel=self._cancel_event, progress=progress
                )
            except Exception:
                art_tasks = []
            for t in art_tasks:
                if self._cancel_event.is_set():
                    break
                try:
                    size = t["size_fn"]() or 0
                except Exception:
                    size = 0
                if size >= MIN_SIZE_BYTES:
                    results.append((t, size, "artifact"))

        # Eski dosyalar (İndirilenler / Downloads)
        for dlname in ("İndirilenler", "Downloads"):
            d = HOME / dlname
            if d.exists() and not self._cancel_event.is_set():
                progress(_("Scanning old files…"))
                try:
                    old = _tasks_mod.make_old_files_tasks(str(d), 90)
                except Exception:
                    old = []
                for t in old:
                    try:
                        size = t["size_fn"]() or 0
                    except Exception:
                        size = 0
                    if size >= MIN_SIZE_BYTES:
                        results.append((t, size, "oldfile"))
                break

        # Blacklist filtre
        results = [
            (t, s, k) for t, s, k in results
            if not is_blacklisted(t.get("path", ""))
        ]

        # Skor + neden
        progress(_("Scoring…"))
        enriched = []
        for t, size, kind in results:
            score, reason = compute_score_and_reason(t, size, kind, open_paths)
            enriched.append((t, size, kind, score, reason))
        return enriched

    def _build_rows(
        self,
        groups: dict[str, list],
        singles: list,
        auto_set: set[int],
    ) -> list[SuggestionRow]:
        rows: list[SuggestionRow] = []
        for key, items in groups.items():
            total_size = sum(it[1] for it in items)
            risks = [t["risk"] for t, *_ in items]
            if "high" in risks:
                color = _HIGH_COLOR
            elif "medium" in risks:
                color = _MEDIUM_COLOR
            else:
                color = _LOW_COLOR
            active_count = sum(1 for t, *_ in items if "ACTIVE" in t.get("desc", ""))
            inactive = len(items) - active_count
            items_part = ngettext(
                "{n} item", "{n} items", len(items)
            ).format(n=len(items))
            reason = _(
                "{items_part} · {inactive} old + {active} active"
            ).format(items_part=items_part, inactive=inactive, active=active_count)
            score = max(int(it[3]) for it in items)
            group_row = SuggestionRow(
                tid=-1,
                name=f"{key} ({items_part})",
                score=score,
                size_bytes=total_size,
                size_text=human(total_size),
                reason=reason,
                risk_color=color,
                kind="group",
                is_group=True,
            )
            for task, size, kind, sc, rs in items:
                tid = self._next_tid
                self._next_tid += 1
                self.tasks[tid] = task
                child_color = _RISK_COLOR_MAP.get(
                    task.get("risk", "medium"), _MEDIUM_COLOR
                )
                group_row.children.append(SuggestionRow(
                    tid=tid,
                    name=task.get("name", "?"),
                    score=int(sc),
                    size_bytes=size,
                    size_text=human(size),
                    reason=rs,
                    risk_color=child_color,
                    kind=kind,
                    is_group=False,
                    checked=id(task) in auto_set,
                ))
            rows.append(group_row)

        for task, size, kind, sc, rs in singles:
            tid = self._next_tid
            self._next_tid += 1
            self.tasks[tid] = task
            color = _RISK_COLOR_MAP.get(task.get("risk", "medium"), _MEDIUM_COLOR)
            rows.append(SuggestionRow(
                tid=tid,
                name=task.get("name", "?"),
                score=int(sc),
                size_bytes=size,
                size_text=human(size),
                reason=rs,
                risk_color=color,
                kind=kind,
                is_group=False,
                checked=id(task) in auto_set,
            ))
        return rows

    # ---- Internals — clean ----

    def _clean_thread(
        self, selected: list[tuple[int, int, dict[str, Any]]]
    ) -> None:
        for n, (gi, ci, task) in enumerate(selected, 1):
            if self._cancel_event.is_set():
                self.on_log(
                    _("Cancelled: {done}/{total} done").format(
                        done=n - 1, total=len(selected),
                    )
                    + "\n"
                )
                break
            self.on_progress(
                f"{n} / {len(selected)} — {task.get('name', '')}"
            )
            self.on_log(f"▶ {task['name']}\n")
            try:
                rc, out = task["clean_fn"]()
            except Exception as e:
                rc, out = 1, _("exception: {err}").format(err=e)
            status = "✓" if rc == 0 else "✗"
            self.on_log(f"  {status} {out.strip()[:200]}\n")
            self._mark_done(gi, ci, rc)
        self._set_busy(False, "")
        self.on_disk_label_dirty()
        self.on_log("--- " + _("Smart cleanup complete") + " ---\n")
        events.emit("clean.finished", panel="suggestion")

    def _mark_done(self, gi: int, ci: int, rc: int) -> None:
        marker = "✓ " if rc == 0 else "✗ "
        if ci < 0:
            if 0 <= gi < len(self.rows):
                row = self.rows[gi]
                row.checked = False
                row.status_marker = marker
                self.on_row_updated(gi, -1, row)
        else:
            if 0 <= gi < len(self.rows) and 0 <= ci < len(self.rows[gi].children):
                child = self.rows[gi].children[ci]
                child.checked = False
                child.status_marker = marker
                self.on_row_updated(gi, ci, child)
        self._emit_total()

    # ---- Internals — selection ----

    def _set_all(self, val: bool) -> None:
        for gi, row in enumerate(self.rows):
            row.checked = val
            self.on_row_updated(gi, -1, row)
            for ci, child in enumerate(row.children):
                child.checked = val
                self.on_row_updated(gi, ci, child)
        self._emit_total()

    def _emit_total(self) -> None:
        self.on_total_changed(self.selected_count, self.total_bytes)

    def _set_busy(self, busy: bool, txt: str) -> None:
        self._busy = busy
        self.on_busy_changed(busy, txt)


# ---- helpers (modül seviyesi) ----

# Risk renkleri (RISK_COLORS'tan kopya — ui katmanına bağımlılık yok)
_LOW_COLOR = "#1a7f37"
_MEDIUM_COLOR = "#bf8700"
_HIGH_COLOR = "#cf222e"
_RISK_COLOR_MAP = {"low": _LOW_COLOR, "medium": _MEDIUM_COLOR, "high": _HIGH_COLOR}


def _group_enriched(
    enriched: list[tuple[dict[str, Any], int, str, float, str]],
) -> tuple[dict[str, list], list]:
    """Artefakt türlerini grupla; sistem/oldfile tekil kalır.

    Tek öğeli gruplar açılır (singles'a karışır).
    """
    groups: dict[str, list] = {}
    singles: list = []
    for tup in enriched:
        task, _size, kind, _score, _reason = tup
        if kind == "artifact":
            bn = os.path.basename(task.get("path", "")) or "?"
            key = f"📦 {bn}"
            groups.setdefault(key, []).append(tup)
        else:
            singles.append(tup)
    final_groups: dict[str, list] = {}
    for key, items in groups.items():
        if len(items) <= 1:
            singles.extend(items)
        else:
            final_groups[key] = items
    return final_groups, singles


def _compute_auto_select(
    groups: dict[str, list], singles: list,
) -> set[int]:
    """Top-N + skor eşiği + kümülatif cap — id(task) seti döner."""
    all_items: list[tuple[dict[str, Any], int, str, float, str, str | None]] = []
    for key, items in groups.items():
        for t, size, kind, sc, rs in items:
            all_items.append((t, size, kind, sc, rs, key))
    for t, size, kind, sc, rs in singles:
        all_items.append((t, size, kind, sc, rs, None))
    all_items.sort(key=lambda x: -x[3])

    cap = AUTO_SELECT_MAX_GB * (1024 ** 3)
    auto_set: set[int] = set()
    cumulative = 0
    picked = 0
    for t, size, kind, sc, rs, _key in all_items:
        if picked >= AUTO_SELECT_TOP_N:
            break
        if cumulative + size > cap:
            continue
        if sc < AUTO_SELECT_MIN_SCORE:
            continue
        if t.get("risk", "") != "low":
            continue
        if "ACTIVE" in t.get("desc", ""):
            continue
        if "currently open" in (rs or ""):
            continue
        auto_set.add(id(t))
        cumulative += size
        picked += 1
    return auto_set


def _coerce_growth(raw: dict | None) -> GrowthInfo | None:
    if not raw or not raw.get("growth"):
        return None
    items = [
        GrowthItem(
            path=g["path"], name=g.get("name", ""),
            current_size=g["current_size"], prev_size=g["prev_size"],
            delta=g["delta"], ratio=g["ratio"],
        )
        for g in raw["growth"]
    ]
    return GrowthInfo(prev_scanned_at=raw["prev_scanned_at"], items=items)


def _noop(*_a, **_kw) -> None:
    pass


def _noop2(*_a, **_kw) -> None:
    pass


def _noop3(*_a, **_kw) -> None:
    pass


__all__ = [
    "AUTO_SELECT_MAX_GB",
    "AUTO_SELECT_MIN_SCORE",
    "AUTO_SELECT_TOP_N",
    "CleanPreview",
    "ExportRow",
    "GrowthInfo",
    "GrowthItem",
    "MIN_SIZE_BYTES",
    "SuggestionController",
    "SuggestionRow",
]
