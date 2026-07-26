# T001 Research Findings: HTTP Static-File Serving in ServerTransport

Status: resolved • Date: 2026-07-26

## 1. Current Transport Setup

`ServerTransport` (`src/dros/_transport.py:60`) creates a `socketio.Server(async_mode="threading")`, wraps it in `socketio.WSGIApp(sio)`, and serves it via `werkzeug.serving.make_server(host, port, app, threaded=True)`. The WSGI app currently routes only Socket.IO traffic — any regular HTTP request returns a 404 from python-socketio’s default WSGI handler.

The WSGI server runs in a daemon thread (`self._wsgi_thread`). `werkzeug.make_server(threaded=True)` uses `ThreadingMixIn` to spawn a thread per request.

## 2. What python-socketio Provides Out of the Box

`socketio.WSGIApp` (the same WSGI wrapper already used) supports two mechanisms:

### a) `static_files` dict

```python
app = socketio.WSGIApp(sio, static_files={
    '/': 'path/to/dashboard.html',
    '/static/app.js': 'path/to/static/app.js',
})
```

Maps exact URL paths to filesystem paths. Routing precedence: Socket.IO endpoint → static files → 404 (or `other_wsgi_app`). The server automatically determines content type from file extension.

Unsupported: directory listings, `index.html` fallback on directories, serving entire directory trees under a prefix.

### b) `other_wsgi_app` parameter

```python
app = socketio.WSGIApp(sio, other_wsgi_app=my_wsgi_app)
```

Forwards non-Socket.IO traffic to another WSGI app. This is where static file middleware plugs in.

## 3. Recommended Approach

Choice depends on the serving needs:

| Need | Approach |
|------|----------|
| Single HTML file (e.g. dashboard) | `WSGIApp(sio, static_files={'/': 'static/dashboard.html'})` |
| Multiple files / entire directory | `werkzeug.SharedDataMiddleware` as `other_wsgi_app` |

### Approach A: `static_files` dict (single-file, zero new code)

```python
# In ServerTransport.start(), replace:
app = socketio.WSGIApp(self._sio)

# With:
static_files = {}
if self._static_dir:
    import os
    static_files = {
        f"/{name}": os.path.join(self._static_dir, name)
        for name in os.listdir(self._static_dir)
        if os.path.isfile(os.path.join(self._static_dir, name))
    }
app = socketio.WSGIApp(self._sio, static_files=static_files)
```

This is the simplest possible change. The `static_files` dict is passed once at `WSGIApp` construction time — no runtime overhead.

### Approach B: `SharedDataMiddleware` (directory serving, more flexible)

```python
from werkzeug.middleware.shared_data import SharedDataMiddleware

# Wrap socket.io WSGI app in static file middleware
sio_app = socketio.WSGIApp(self._sio)
app = SharedDataMiddleware(sio_app, {
    '/static': self._static_dir,
})
```

This serves files under `/static/` from `self._static_dir`. Supports index files, subdirectories, and proper content-type detection. Falls through to `sio_app` for paths not matching `/static/*`.

**Caveat**: `SharedDataMiddleware` wraps the app, so the Socket.IO endpoint still gets checked within the inner `WSGIApp`. This means Socket.IO traffic flows: `SharedDataMiddleware` → `WSGIApp` → socket.io. Static traffic flows: `SharedDataMiddleware` → serve file. This works because `SharedDataMiddleware` only intercepts matching prefixes.

## 4. Threading Concerns

**No new concerns.** The existing setup already handles concurrency:

- `werkzeug.make_server(threaded=True)` uses `ThreadingMixIn`, which spawns a thread for each incoming HTTP request.
- Static file serving is I/O bound (read file, write response). The GIL is released during I/O.
- For the dashboard use case (serving a small HTML page on occasional browser loads), there's zero performance risk.
- Socket.IO long-polling threads and static-file threads share the same pool — if many long-poll clients are connected, static file requests may queue behind them. Mitigation: this is standard for development servers and matches the current risk profile.

No additional locks or synchronization needed.

## 5. Specific Code Changes (Approach A — minimal)

In `ServerTransport.__init__`, add a parameter:

```python
def __init__(
    self,
    host: str = "0.0.0.0",
    port: int = 0,
    *,
    ping_timeout: float = 2.0,
    ping_interval: float = 5.0,
    static_dir: str | None = None,  # NEW
) -> None:
    ...
    self._static_dir = static_dir
```

In `ServerTransport.start()`, build the `static_files` dict:

```python
static_files: dict[str, str] = {}
if self._static_dir and os.path.isdir(self._static_dir):
    for name in os.listdir(self._static_dir):
        fpath = os.path.join(self._static_dir, name)
        if os.path.isfile(fpath):
            static_files[f"/{name}"] = fpath

app = socketio.WSGIApp(self._sio, static_files=static_files)
```

Usage:

```python
transport = ServerTransport(port=5000, static_dir="static/")
```

## 6. Alternative Approaches Considered

### Separate HTTP server on different port
Rejected: adds complexity, requires opening another port, and the whole point is serving a simple dashboard alongside socket.io on the same connection.

### Custom WSGI middleware from scratch
Rejected: `werkzeug.SharedDataMiddleware` already exists and is battle-tested. `werkzeug` is already a dependency of `dros`.

### Mounting a WSGI framework (Flask, etc.)
Rejected: overpowered. The dashboard is a static HTML page with CDN-loaded JS. No server-side templating or routing needed.

### `other_wsgi_app` with `SharedDataMiddleware`
This works and is more flexible than `static_files` when serving a directory tree. But for the current use case (a single `dashboard.html`), `static_files` is simpler and requires no extra imports beyond what’s already used.

## 7. Dependencies

- **No new dependencies.** `werkzeug` (≥3) is already a required dependency of `dros`. `socketio.WSGIApp.static_files` is built into `python-socketio` (≥5).
- `os` and `os.path` are stdlib.