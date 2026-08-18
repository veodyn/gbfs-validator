"""Serves a fixture feed directory over HTTP so tests can exercise real fetching.

`{BASE}` in any served body is replaced by the server's own base URL, which is
how fixture feeds reference their sibling files without hardcoding a port.
"""

from __future__ import annotations

import contextlib
import functools
import http.server
import pathlib
import threading
from collections.abc import Iterator
from typing import Any


class _Handler(http.server.BaseHTTPRequestHandler):
    def __init__(
        self,
        feed_dir: pathlib.Path,
        base: str,
        capture: list[dict[str, str]] | None,
        *args: object,
        **kwargs: object,
    ) -> None:
        self.feed_dir = feed_dir
        self.base = base
        self.capture = capture
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    def log_message(self, format: str, *args: Any) -> None:  # pyright: ignore[reportImplicitOverride]  # noqa: A002
        pass

    def do_GET(self) -> None:
        name = self.path.lstrip("/")
        if self.capture is not None:
            self.capture.append({"path": self.path, **dict(self.headers.items())})
        path = self.feed_dir / name
        if name == "meta.json" or not path.is_file():
            self.send_response(404)
            self.end_headers()
            return
        body = path.read_text().replace("{BASE}", self.base).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@contextlib.contextmanager
def serve(
    feed_dir: pathlib.Path,
    capture: list[dict[str, str]] | None = None,
) -> Iterator[str]:
    """Yield the base URL of a server exposing `feed_dir`'s json files."""
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        functools.partial(_Handler, feed_dir, "", None),
    )
    base = f"http://127.0.0.1:{server.server_address[1]}"
    server.RequestHandlerClass = functools.partial(_Handler, feed_dir, base, capture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield base
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
