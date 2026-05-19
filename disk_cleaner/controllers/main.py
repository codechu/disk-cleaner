"""MainController — üst pencere kabuğunun state machine'i.

Sahip olunan:

- Mount listesi ve aktif seçim
- Disk usage parsing (df çıktısı + %dolu renk eşiği)
- BTRFS/ZFS uyarı metinleri
- ``runtime.TRASH_MODE`` / ``runtime.DRY_RUN`` toggle'ları
- Watchdog start/stop/status
- Settings persist (mount + entries)

View'ın görevi: header bar widget'ları, panel oluşturma + wire'lama,
infobar/tray icon. Bu sınıf View'a dokunmaz.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .. import events, runtime
from ..i18n import _
from ..settings import SETTINGS, save_settings
from ..utils import list_real_mounts, run
from ..watchdog.daemon import (
    watchdog_running,
    watchdog_start_background,
    watchdog_stop,
)


@dataclass
class Mount:
    target: str
    source: str
    fstype: str
    size: str
    used: str
    avail: str
    pcent: str


@dataclass
class DiskUsage:
    """Görsel için hazır disk doluluk özeti."""

    total: str     # "468G"
    used: str      # "338G"
    avail: str     # "105G"
    percent: int   # 0..100
    color: str     # "#cf222e" / "#bf8700" / "#1a7f37"

    @property
    def label_markup(self) -> str:
        return (
            f" <span foreground='{self.color}' weight='bold'>"
            f"{self.percent}% {_('full')}</span> "
            f"<span color='#888'>· {self.used} / {self.total}</span>"
        )


# Renk eşikleri
_DISK_RED = 90
_DISK_YELLOW = 75
_COLOR_RED = "#cf222e"
_COLOR_YELLOW = "#bf8700"
_COLOR_GREEN = "#1a7f37"

# Hangi FS'ler kullanıcıya snapshot uyarısı vermeli
_FS_WARN: dict[str, str] = {
    "btrfs": "btdu",
    "zfs": "zfs list -t snapshot",
}


class MainController:
    """Ana pencere state machine'i — View-bağımsız."""

    def __init__(self) -> None:
        # Mount listesi
        raw = list_real_mounts() or []
        self.mounts: list[Mount] = [
            Mount(
                target=m.get("target", ""),
                source=m.get("source", ""),
                fstype=m.get("fstype", ""),
                size=m.get("size", "?"),
                used=m.get("used", "?"),
                avail=m.get("avail", "?"),
                pcent=m.get("pcent", "?"),
            )
            for m in raw
        ] or [Mount("/", "", "", "?", "?", "?", "?")]

        # Aktif mount — settings'ten oku, yoksa "/" veya ilk mount
        default = SETTINGS.get("mount", "/")
        if not any(m.target == default for m in self.mounts):
            default = (
                "/" if any(m.target == "/" for m in self.mounts)
                else self.mounts[0].target
            )
        self.current_mount: str = default

        # Trash/Dry başlangıç durumu settings'ten
        runtime.TRASH_MODE = SETTINGS.get("trash_mode", True)
        runtime.DRY_RUN = SETTINGS.get("dry_run", False)

        # Observers
        self.on_mount_changed: Callable[[str], None] = _noop
        self.on_disk_usage_updated: Callable[[DiskUsage | None], None] = _noop
        self.on_trash_mode_changed: Callable[[bool], None] = _noop
        self.on_dry_run_changed: Callable[[bool], None] = _noop
        self.on_watchdog_status_changed: Callable[[bool], None] = _noop
        self.on_log: Callable[[str], None] = _noop
        self.on_fs_warning_changed: Callable[[str | None], None] = _noop

    # ---- Mount ----

    def set_mount(self, target: str) -> None:
        if target == self.current_mount:
            return
        self.current_mount = target
        SETTINGS["mount"] = target
        save_settings(SETTINGS)
        self.on_mount_changed(target)
        self.on_fs_warning_changed(self.fs_warning_for(target))
        self.refresh_disk_usage()
        events.emit("mount.changed", target=target)

    def find_mount(self, target: str) -> Mount | None:
        for m in self.mounts:
            if m.target == target:
                return m
        return None

    def fs_warning_for(self, target: str) -> str | None:
        m = self.find_mount(target)
        if not m:
            return None
        fst = m.fstype.lower()
        tool = _FS_WARN.get(fst)
        if not tool:
            return None
        return _(
            "⚠  {fs} filesystem — `du`/`df` hide the real space used by "
            "snapshots. To inspect snapshots use: {tool}"
        ).format(fs=fst.upper(), tool=tool)

    # ---- Disk usage ----

    def refresh_disk_usage(self) -> None:
        usage = read_disk_usage(self.current_mount)
        self.on_disk_usage_updated(usage)

    # ---- Trash / Dry ----

    def set_trash_mode(self, val: bool) -> None:
        runtime.TRASH_MODE = val
        SETTINGS["trash_mode"] = val
        save_settings(SETTINGS)
        if val:
            msg = _("Trash mode: ON (recoverable)")
        else:
            msg = _("Trash mode: OFF (permanent deletion!)")
        self.on_log(msg + "\n")
        self.on_trash_mode_changed(val)
        events.emit("settings.changed", key="trash_mode", value=val)

    def set_dry_run(self, val: bool) -> None:
        runtime.DRY_RUN = val
        SETTINGS["dry_run"] = val
        save_settings(SETTINGS)
        if val:
            msg = _("Dry-run: ON (nothing will be deleted)")
        else:
            msg = _("Dry-run: OFF")
        self.on_log(msg + "\n")
        self.on_dry_run_changed(val)
        events.emit("settings.changed", key="dry_run", value=val)

    # ---- Watchdog ----

    def watchdog_status(self) -> bool:
        return watchdog_running()

    def toggle_watchdog(self) -> None:
        if watchdog_running():
            watchdog_stop()
            self.on_log(_("Watchdog stopped.") + "\n")
        else:
            if watchdog_start_background():
                self.on_log(
                    _(
                        "Watchdog started (threshold {pct}%, every {interval}s)."
                    ).format(
                        pct=SETTINGS.get("watchdog_threshold", 85),
                        interval=SETTINGS.get("watchdog_interval", 600),
                    )
                    + "\n"
                )
            else:
                self.on_log(_("Watchdog is already running.") + "\n")
        self.on_watchdog_status_changed(watchdog_running())

    # ---- Settings persist ----

    def save_panel_entries(self, entries: dict[str, str]) -> None:
        """View tarafındaki panel entry'leri toplu kaydet."""
        SETTINGS["entries"] = entries
        SETTINGS["mount"] = self.current_mount
        SETTINGS["trash_mode"] = runtime.TRASH_MODE
        SETTINGS["dry_run"] = runtime.DRY_RUN
        save_settings(SETTINGS)


def read_disk_usage(mount: str) -> DiskUsage | None:
    """``df -h`` parse — okunabilir özet + renk önerisi."""
    rc, out = run(["df", "-h", "--output=size,used,avail,pcent", mount])
    if rc != 0:
        return None
    lines = out.strip().splitlines()
    if len(lines) < 2:
        return None
    parts = lines[1].split()
    if len(parts) < 4:
        return None
    try:
        pcent = int(parts[3].rstrip("%"))
    except ValueError:
        pcent = 0
    if pcent >= _DISK_RED:
        color = _COLOR_RED
    elif pcent >= _DISK_YELLOW:
        color = _COLOR_YELLOW
    else:
        color = _COLOR_GREEN
    return DiskUsage(
        total=parts[0], used=parts[1], avail=parts[2],
        percent=pcent, color=color,
    )


def _noop(*_a, **_kw) -> None:
    pass


__all__ = ["DiskUsage", "MainController", "Mount", "read_disk_usage"]
