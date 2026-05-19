# Control API

Disk Cleaner runs (when its GUI is open) a Unix-domain JSON-line server on:

```
$XDG_RUNTIME_DIR/disk_cleaner/control.sock
# (typically: /run/user/$(id -u)/disk_cleaner/control.sock)
```

Every request is a single JSON object with at least a `"cmd"` key,
followed by a newline. The response is one JSON object per line.

> **Security note.** The destructive `clean` command path is **not**
> exposed over the API by design — only the GUI can perform destructive
> operations. Anything that mutates the filesystem must be triggered by
> a user click.

## Commands

| `cmd`                | Purpose                                            |
|----------------------|----------------------------------------------------|
| `screenshot`         | Returns a base64-encoded PNG screenshot of the window |
| `list_tabs`          | Lists tab names                                    |
| `set_tab`            | Switches to a specific tab                         |
| `list_cleanup_modes` | Lists the automatic modes available under "Smart scan" |
| `select_cleanup_mode`| Selects an automatic cleanup mode                  |
| `click`              | Clicks a widget by label or name                   |
| `click_at`           | Clicks at the (x, y) coordinate                    |
| `mouse_move`         | Moves the mouse cursor to (x, y)                   |
| `set_entry`          | Sets a text input                                  |
| `set_check`          | Checks/unchecks a checkbox                         |
| `get_state`          | Summary of the current window/tab/UI state         |
| `window`             | Queries window size / position                     |
| `debug`              | Detailed state dump for development (incl. `bus_stats`) |
| `subscribe`          | Subscribe to the event stream — push, multichannel, heartbeat |
| `exit`               | Exits the application                              |

## Example

```bash
echo '{"cmd":"list_tabs"}' | nc -U $XDG_RUNTIME_DIR/disk_cleaner/control.sock
```

## Error responses

A bad request returns `{"ok": false, "error": "..."}`; successful
responses follow a command-specific schema.

## Event stream — `subscribe`

A one-way stream that pushes events instead of forcing the client to poll:

```json
→ {"cmd":"subscribe","types":["scan.*","treemap.drill"],"heartbeat_sec":5.0}
← {"ok":true,"subscribed":["scan.*","treemap.drill"],"heartbeat_sec":5.0}
← {"event":"scan.started","ts":1234567890.1,"panel":"suggestion"}
← {"event":"scan.finished","ts":1234567892.4,"panel":"suggestion","count":42,"groups":3}
← {"event":"treemap.drill","ts":1234567895.0,"direction":"in","from_path":"/home","to_path":"/home/user"}
← {"event":"_keepalive","ts":1234567900.0}
...
```

**Behavior**:

- `subscribe` is terminal on the connection — no further commands are accepted.
- The subscription is removed automatically when the connection closes.
- `types` is a list of glob filters (default `["*"]`).
- `heartbeat_sec` (default 5.0): a `_keepalive` event is emitted every
  N seconds so the client can detect idle connections. Set to `0` to disable.
- **Backpressure**: if the subscriber is slow the queue fills up and new
  events are dropped (visible via `debug bus_stats`). The publisher never blocks.
- Up to 64 concurrent subscribers; exceeding the limit yields `{"ok":false,"error":"limit:..."}`.

### Event types

| Type | Fields |
|---|---|
| `scan.started` | `panel` (system/suggestion/artifacts/explorer/...) |
| `scan.finished` | `panel`, `count`, `cancelled`, optional `groups` |
| `clean.started` | `panel`, `count` |
| `clean.finished` | `panel` |
| `treemap.scan.started` | `path` |
| `treemap.scan.finished` | `path`, `size` (bytes), `ok` |
| `treemap.drill` | `direction` (in/up/to), `from_path`, `to_path` |
| `mount.changed` | `target` |
| `settings.changed` | `key` (trash_mode/dry_run/viz_mode), `value` |
| `prefs.language.changed` | `source=user`, `channel=prefs`, `old`, `new` |
| `prefs.theme.changed` | `source=user`, `channel=prefs`, `old`, `new` |
| `_keepalive` | (just `ts`) |
| `_closed` | server-shutdown sentinel (rarely seen) |

### Bash example

```bash
SOCK=$XDG_RUNTIME_DIR/disk_cleaner/control.sock
( echo '{"cmd":"subscribe","types":["scan.*"]}'; cat ) | nc -U "$SOCK"
# scan start/finish events stream live
```

### Python example (asyncio)

```python
import asyncio, json, os

async def listen():
    sock = os.environ["XDG_RUNTIME_DIR"] + "/disk_cleaner/control.sock"
    reader, writer = await asyncio.open_unix_connection(sock)
    writer.write(b'{"cmd":"subscribe","types":["*"]}\n')
    await writer.drain()
    async for line in reader:
        ev = json.loads(line)
        print(ev["event"], ev.get("panel", ""))

asyncio.run(listen())
```

### Stats / debug

```json
→ {"cmd":"debug","target":"bus_stats"}
← {"ok":true,"stats":{"subscribers":1,"max_subscribers":64,"total_emitted":17,
                       "details":[{"types":["scan.*"],"queue_depth":0,"queue_max":200,
                                   "received":4,"dropped":0,"age_sec":12.3}]}}
```
