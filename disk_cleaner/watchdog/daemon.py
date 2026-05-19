"""Watchdog daemon — monitors disk fullness in the background.

A single instance is guaranteed via the PID file. When the threshold is
exceeded, sends a user notification via ``notify-send`` (cooldown
prevents spam).

The legacy entry (``disk_cleaner.py --watchdog``) is preserved; the
fork opens a new session via ``start_new_session=True`` so the daemon
survives the GUI closing.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from ..config import DATA_DIR, WATCHDOG_PID
from ..i18n import _
from ..settings import SETTINGS
from ..utils import run

WATCHDOG_PID_FILE: Path = WATCHDOG_PID  # $XDG_RUNTIME_DIR/disk_cleaner/watchdog.pid
WATCHDOG_LOG: Path = DATA_DIR / "watchdog.log"  # $XDG_DATA_HOME/disk_cleaner/watchdog.log


def disk_percent(target: str = "/") -> int | None:
    """Read the mount percentage via ``df``. Error → None."""
    rc, out = run(["df", "--output=pcent", target])
    if rc != 0:
        return None
    lines = out.strip().splitlines()
    if len(lines) < 2:
        return None
    try:
        return int(lines[1].strip().rstrip("%"))
    except ValueError:
        return None


def notify(title: str, body: str, urgency: str = "normal", icon: str | None = None) -> None:
    """Wrapper for ``notify-send``."""
    cmd = ["notify-send", "-u", urgency, "-a", _("Disk Cleaner")]
    if icon:
        cmd += ["-i", icon]
    cmd += [title, body]
    run(cmd, timeout=5)


def watchdog_running() -> bool:
    """Is the watchdog currently running? (PID liveness check.)"""
    if not WATCHDOG_PID_FILE.exists():
        return False
    try:
        pid = int(WATCHDOG_PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return False
    try:
        os.kill(pid, 0)  # signal 0 = liveness check
        return True
    except OSError:
        return False


def watchdog_stop() -> bool:
    """Stop via SIGTERM. Returns True on success."""
    if not WATCHDOG_PID_FILE.exists():
        return False
    try:
        pid = int(WATCHDOG_PID_FILE.read_text().strip())
        os.kill(pid, 15)  # SIGTERM
        WATCHDOG_PID_FILE.unlink()
        return True
    except (ValueError, OSError):
        return False


def watchdog_start_background(entry_script: str | None = None) -> bool:
    """Start the watchdog as a background process. False if already present.

    Spawned as ``python -m disk_cleaner --watchdog`` so the same code
    path works under pip installs, AppImage, snap, and dev checkouts —
    no fragile path to a shim script file.
    """
    if watchdog_running():
        return False
    env = os.environ.copy()
    # Ensure the runtime + data directories exist so the log/pid writes
    # below don't fail on a fresh install.
    WATCHDOG_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATCHDOG_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_fp = open(WATCHDOG_LOG, "ab")
    proc = subprocess.Popen(
        [sys.executable, "-m", "disk_cleaner", "--watchdog"],
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )
    WATCHDOG_PID_FILE.write_text(str(proc.pid))
    return True


def watchdog_loop() -> None:
    """Infinite loop: periodic disk check + notification."""
    threshold = int(SETTINGS.get("watchdog_threshold", 85))
    interval = int(SETTINGS.get("watchdog_interval", 600))
    cooldown = int(SETTINGS.get("watchdog_cooldown", 3600))
    last_notify_at: float = 0
    last_pct = -1
    sys.stdout.write(f"watchdog up: threshold={threshold}% interval={interval}s\n")
    sys.stdout.flush()
    while True:
        try:
            pct = disk_percent("/")
            if pct is not None and pct != last_pct:
                sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] / = {pct}%\n")
                sys.stdout.flush()
                last_pct = pct
            now = time.time()
            if pct is not None and pct >= threshold and (now - last_notify_at) >= cooldown:
                notify(
                    _("💾 Disk almost full"),
                    _(
                        "/ is {pct}% full. Would you like to open Disk Cleaner and free up space?"
                    ).format(pct=pct),
                    urgency="critical",
                )
                last_notify_at = now
        except Exception as e:
            sys.stdout.write(f"error: {e}\n")
            sys.stdout.flush()
        time.sleep(interval)


# Backward-compatible names
_disk_percent = disk_percent

__all__ = [
    "WATCHDOG_LOG",
    "WATCHDOG_PID_FILE",
    "disk_percent",
    "notify",
    "watchdog_loop",
    "watchdog_running",
    "watchdog_start_background",
    "watchdog_stop",
]
