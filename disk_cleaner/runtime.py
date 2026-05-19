"""Runtime mutable global'ler.

UI tarafından değiştirilen, alt modüller tarafından çağrı anında
okunan iki durum bayrağı:

- :data:`TRASH_MODE` — Çöp kutusu modu. True ise silme yerine
  ``gio trash`` kullanılır (geri alınabilir).
- :data:`DRY_RUN` — Test modu. True ise temizleme komutları
  çalıştırılmaz, sadece "[KURU] silinecekti: …" loglanır.

**Neden modül global'i?** Bu değerler kullanıcı toggle'larıyla
runtime'da değişir, ama hemen hemen her temizleyici çağrısında
okunur. DI ile her aşamada propagate etmek yerine tek bir paylaşımlı
state modülü kullanmak pratik. Yeni kod ``from .. import runtime``
yapıp ``runtime.TRASH_MODE`` okumalı (import-time'da değil, çağrı
anında — geç bağlama).

İleride :class:`~disk_cleaner.settings.SettingsStore` üstüne typed
accessor olarak taşınabilir.
"""
from __future__ import annotations

#: Çöp kutusu modu (True → ``gio trash``, False → kalıcı silme).
TRASH_MODE: bool = True

#: Dry-run (True → hiçbir şey silinmez, sadece loglanır).
DRY_RUN: bool = False


__all__ = ["DRY_RUN", "TRASH_MODE"]
