# Adding a Scanner

A Scanner produces cleanup candidates (`Task`s) for a single source on
disk (a cache, an artifact, a group of old files, …).

## Steps

### 1. Write the Scanner class

`disk_cleaner/scanners/my_thing.py`:

```python
from __future__ import annotations

from threading import Event
from typing import Callable, Iterable, Optional

from .base import Scanner, Task
from ..cleaners.contents import ContentsCleaner  # or your own Cleaner


class MyThingScanner(Scanner):
    name = "mything"

    def list_tasks(
        self,
        *,
        cancel: Optional[Event] = None,
        progress: Optional[Callable[[str], None]] = None,
    ) -> Iterable[Task]:
        if progress:
            progress("Scanning MyThing…")

        path = "~/.cache/mything"
        yield Task(
            name="MyThing cache",
            desc="Download cache for the MyThing tool.",
            risk="low",
            path=path,
            kind="system",
            size_fn=lambda: __import__("disk_cleaner.core.sizing",
                                      fromlist=["dir_size"]).dir_size(path),
            cleaner=ContentsCleaner(path),
        )
```

### 2. Register with AppContext

Add it to the scanner dict in `disk_cleaner/app.py`:

```python
self.scanners["mything"] = MyThingScanner()
```

### 3. Honor cancel + progress

- At the top of each long loop, `if cancel and cancel.is_set(): break`.
- The `progress` callback should receive short, human-readable text; the
  UI displays it directly.

### 4. Write a test

`tests/test_scanners.py`:

```python
def test_mything_scanner_basic(tmp_path):
    from disk_cleaner.scanners.my_thing import MyThingScanner
    s = MyThingScanner()
    tasks = list(s.list_tasks())
    assert all(t.kind == "system" for t in tasks)
```

### 5. Document it

- One line in the README or the CHANGELOG.
- Set `risk` correctly — "low" only for reversible / cache contents;
  use "medium" / "high" when user data is involved, which prompts the UI
  to ask for confirmation.
