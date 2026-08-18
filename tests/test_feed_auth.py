"""End-to-end auth: the four upstream modes driven through `GBFS(url, auth=...)`.

`tests/test_fetch.py` covers the header building; these drive a whole feed so a
regression in the wiring from the constructor to every fetched file, including
the OAuth priming call that runs before autodiscovery, cannot pass unnoticed.
"""

from __future__ import annotations

import base64
import contextlib
import http.server
import pathlib
import threading
from collections.abc import Iterator
from typing import Any

import pytest

from conftest import write_feed
from fixtureserver import serve
from gbfs_validator import GBFS
from gbfs_validator.fetch import USER_AGENT

# Every file this fixture feed actually fetches: the discovery document and the
# one file its `feeds` array lists.
FEED_PATHS = ["/gbfs.json", "/system_information.json"]

BASIC_CREDENTIALS = base64.b64encode(b"u:p").decode()


@pytest.fixture
def feed_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    return write_feed(tmp_path, "{BASE}")


def _validate(feed_dir: pathlib.Path, auth: dict[str, Any], log: list[dict[str, str]]) -> None:
    """Run a full validation over the served feed, asserting it really ran."""
    with serve(feed_dir, log) as base:
        report = GBFS(base + "/gbfs.json", auth=auth).validation()
    assert report["summary"]["hasErrors"] is False
    served = {entry["file"]: entry for entry in report["files"] if entry.get("exists")}
    assert set(served) == {"gbfs.json", "system_information.json"}


def _feed_requests(log: list[dict[str, str]]) -> list[dict[str, str]]:
    requests = [entry for entry in log if entry["path"] in FEED_PATHS]
    assert [entry["path"] for entry in requests] == FEED_PATHS
    return requests


def test_basic_auth_replaces_headers_for_every_fetched_file(feed_dir: pathlib.Path) -> None:
    """Upstream replaces the whole header object, so the User-Agent goes away."""
    auth = {"type": "basic_auth", "basicAuth": {"user": "u", "password": "p"}}
    log: list[dict[str, str]] = []
    _validate(feed_dir, auth, log)
    for request in _feed_requests(log):
        assert request["Authorization"] == f"basic {BASIC_CREDENTIALS}"
        assert request.get("User-Agent") != USER_AGENT


def test_bearer_token_replaces_headers_for_every_fetched_file(feed_dir: pathlib.Path) -> None:
    auth = {"type": "bearer_token", "bearerToken": {"token": "tok"}}
    log: list[dict[str, str]] = []
    _validate(feed_dir, auth, log)
    for request in _feed_requests(log):
        assert request["Authorization"] == "Bearer tok"
        assert request.get("User-Agent") != USER_AGENT


def test_headers_auth_adds_its_headers_and_keeps_the_user_agent(feed_dir: pathlib.Path) -> None:
    auth = {"type": "headers", "headers": [{"key": "X-Api-Key", "value": "secret"}]}
    log: list[dict[str, str]] = []
    _validate(feed_dir, auth, log)
    for request in _feed_requests(log):
        assert request["X-Api-Key"] == "secret"
        assert request["User-Agent"] == USER_AGENT
        assert "Authorization" not in request


@contextlib.contextmanager
def _token_server(log: list[dict[str, str]], payload: bytes) -> Iterator[str]:
    """A client-credentials token endpoint, logging into the same list as the feed."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # pyright: ignore[reportImplicitOverride]  # noqa: A002
            pass

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            log.append(
                {"path": self.path, "body": self.rfile.read(length).decode(), **dict(self.headers)}
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/token"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_oauth_primes_the_token_before_autodiscovery_then_sends_it(feed_dir: pathlib.Path) -> None:
    log: list[dict[str, str]] = []
    with _token_server(log, b'{"access_token": "abc"}') as token_url:
        auth = {
            "type": "oauth_client_credentials_grant",
            "oauthClientCredentialsGrant": {
                "user": "u",
                "password": "p",
                "tokenUrl": token_url,
            },
        }
        _validate(feed_dir, auth, log)

    # The grant must be the first request of the run: gbfs.js primes before it
    # touches the feed, and a token fetched afterwards would be too late.
    assert log[0]["path"] == "/token"
    assert log[0]["body"] == "grant_type=client_credentials"
    assert log[0]["Authorization"] == f"Basic {BASIC_CREDENTIALS}"
    for request in _feed_requests(log):
        assert request["Authorization"] == "Bearer abc"
        assert request.get("User-Agent") != USER_AGENT
