"""Watchdog daemon — disk doluluğunu arka planda izler.

Tek instance PID dosyası ile garanti edilir. Eşik aşılınca
``notify-send`` ile kullanıcıya bildirim atar (cooldown ile spam önler).

Eski entry'yi (``disk_cleaner.py --watchdog``) korur; fork
``start_new_session=True`` ile yeni süreç grubu açar, GUI kapansa bile
yaşamaya devam eder.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from ..config import DATA_DIR, RUNTIME_DIR, WATCHDOG_PID
from ..i18n import _
from ..settings import SETTINGS
from ..utils import run

WATCHDOG_PID_FILE: Path = WATCHDOG_PID            # $XDG_RUNTIME_DIR/disk_cleaner/watchdog.pid
WATCHDOG_LOG: Path = DATA_DIR / "watchdog.log"   # $XDG_DATA_HOME/disk_cleaner/watchdog.log


def disk_percent(target: str = "/") -> int | None:
    """``df`` üstünden mount yüzdesini oku. Hata → None."""
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
    """``notify-send`` sarmalayıcı."""
    cmd = ["notify-send", "-u", urgency, "-a", _("Disk Cleaner")]
    if icon:
        cmd += ["-i", icon]
    cmd += [title, body]
    run(cmd, timeout=5)


def watchdog_running() -> bool:
    """Watchdog şu an çalışıyor mu? (PID liveness)."""
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
    """SIGTERM ile durdur. Başarılıysa True döner."""
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
    """Watchdog'u arka plan süreci olarak başlat. Zaten varsa False."""
    if watchdog_running():
        return False
    # Eski entry'yi çağır — geriye uyum (disk_cleaner.py --watchdog)
    if entry_script is None:
        # Repo kökündeki shim varsayılan
        entry_script = str(Path(__file__).resolve().parents[2] / "disk_cleaner.py")
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, "-B", entry_script, "--watchdog"],
        stdout=open(WATCHDOG_LOG, "ab"),
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )
    WATCHDOG_PID_FILE.write_text(str(proc.pid))
    return True


def watchdog_loop() -> None:
    """Sonsuz döngü: periyodik disk kontrol + bildirim."""
    threshold = int(SETTINGS.get("watchdog_threshold", 85))
    interval = int(SETTINGS.get("watchdog_interval", 600))
    cooldown = int(SETTINGS.get("watchdog_cooldown", 3600))
    last_notify_at: float = 0
    last_pct = -1
    sys.stdout.write(
        f"watchdog up: threshold={threshold}% interval={interval}s\n"
    )
    sys.stdout.flush()
    while True:
        try:
            pct = disk_percent("/")
            if pct is not None and pct != last_pct:
                sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] / = {pct}%\n")
                sys.stdout.flush()
                last_pct = pct
            now = time.time()
            if (
                pct is not None
                and pct >= threshold
                and (now - last_notify_at) >= cooldown
            ):
                notify(
                    _("💾 Disk almost full"),
                    _(
                        "/ is {pct}% full. Would you like to open Disk "
                        "Cleaner and free up space?"
                    ).format(pct=pct),
                    urgency="critical",
                )
                last_notify_at = now
        except Exception as e:
            sys.stdout.write(f"error: {e}\n")
            sys.stdout.flush()
        time.sleep(interval)


# Geriye uyumlu adlar
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
