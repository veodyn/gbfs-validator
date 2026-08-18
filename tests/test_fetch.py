"""Fetcher tests, including upstream's header-replacement auth quirks."""

from __future__ import annotations

import base64
import contextlib
import http.server
import json
import pathlib
import socket
import threading
from collections.abc import Iterator
from typing import Any

import pytest

from fixtureserver import serve
from gbfs_validator.constants.error_ids import AppError, ErrorIds
from gbfs_validator.fetch import USER_AGENT, Fetcher, FetchError

GBFS_BODY = {"last_updated": 1, "ttl": 0, "version": "2.3", "data": {}}


@pytest.fixture
def feed_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "gbfs.json").write_text(json.dumps(GBFS_BODY))
    (tmp_path / "meta.json").write_text(json.dumps({"note": "never served"}))
    (tmp_path / "broken.json").write_text("{not json")
    (tmp_path / "nan.json").write_text('{"ttl": NaN}')
    return tmp_path


def _headers_for(capture: list[dict[str, str]], suffix: str) -> dict[str, str]:
    for request in capture:
        if request["path"].endswith(suffix):
            return request
    raise AssertionError(f"no request for {suffix} in {capture}")


def test_get_json_returns_body(feed_dir: pathlib.Path) -> None:
    with serve(feed_dir) as base:
        assert Fetcher().get_json(base + "/gbfs.json") == GBFS_BODY


def test_missing_file_raises_fetch_error(feed_dir: pathlib.Path) -> None:
    with serve(feed_dir) as base, pytest.raises(FetchError) as excinfo:
        Fetcher().get_json(base + "/missing.json")
    assert excinfo.value.url == base + "/missing.json"
    assert excinfo.value.id is ErrorIds.FETCH_BAD_STATUS
    assert isinstance(excinfo.value, AppError)


def test_meta_json_is_never_served(feed_dir: pathlib.Path) -> None:
    with serve(feed_dir) as base, pytest.raises(FetchError):
        Fetcher().get_json(base + "/meta.json")


def test_file_url_returns_body(feed_dir: pathlib.Path) -> None:
    assert Fetcher().get_json((feed_dir / "gbfs.json").as_uri()) == GBFS_BODY


def test_missing_file_url_raises_fetch_error(feed_dir: pathlib.Path) -> None:
    url = (feed_dir / "absent.json").as_uri()
    with pytest.raises(FetchError) as excinfo:
        Fetcher().get_json(url)
    assert excinfo.value.url == url


def test_unreachable_host_raises_fetch_error() -> None:
    with pytest.raises(FetchError) as excinfo:
        Fetcher(timeout=2.0).get_json("http://127.0.0.1:1/gbfs.json")
    assert excinfo.value.id is ErrorIds.FETCH_UNREACHABLE


BAD_URLS = ["{BASE}/system_information.json", "not a url at all", "", "gopher://example.com/x"]


@pytest.mark.parametrize("url", BAD_URLS)
def test_malformed_or_unsupported_url_raises_fetch_error(url: str) -> None:
    """A feed listing an unusable URL degrades to a missing file, it does not crash."""
    with pytest.raises(FetchError) as excinfo:
        Fetcher(timeout=2.0).get_json(url)
    assert excinfo.value.id is ErrorIds.FETCH_UNREACHABLE
    assert excinfo.value.url == url


@contextlib.contextmanager
def _raw_server(response: bytes) -> Iterator[str]:
    """A socket-level server, for responses http.client rejects before urllib sees them."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(5)
    listener.settimeout(0.2)
    stop = threading.Event()

    def loop() -> None:
        while not stop.is_set():
            try:
                conn, _ = listener.accept()
            except TimeoutError:  # silent-ok: poll so the thread can see `stop`
                continue
            except OSError:
                return
            with conn, contextlib.suppress(OSError):
                conn.recv(65536)
                conn.sendall(response)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{listener.getsockname()[1]}"
    finally:
        stop.set()
        thread.join()
        listener.close()


def test_truncated_body_raises_fetch_error() -> None:
    """http.client.IncompleteRead is not an OSError, so it needs catching explicitly."""
    response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: 50\r\n"
        b"\r\n"
        b'{"last_updated": 1'
    )
    with _raw_server(response) as base, pytest.raises(FetchError) as excinfo:
        Fetcher(timeout=5.0).get_json(base + "/gbfs.json")
    assert excinfo.value.id is ErrorIds.FETCH_UNREACHABLE


def test_garbage_status_line_raises_fetch_error() -> None:
    with _raw_server(b"NOT-HTTP garbage\r\n\r\n") as base, pytest.raises(FetchError) as excinfo:
        Fetcher(timeout=5.0).get_json(base + "/gbfs.json")
    assert excinfo.value.id is ErrorIds.FETCH_UNREACHABLE


def test_invalid_json_raises_fetch_error(feed_dir: pathlib.Path) -> None:
    with serve(feed_dir) as base, pytest.raises(FetchError) as excinfo:
        Fetcher().get_json(base + "/broken.json")
    assert excinfo.value.id is ErrorIds.FETCH_BAD_JSON


def test_nan_literal_is_rejected(feed_dir: pathlib.Path) -> None:
    """JS JSON.parse rejects NaN/Infinity; Python's json accepts them by default."""
    with serve(feed_dir) as base, pytest.raises(FetchError) as excinfo:
        Fetcher().get_json(base + "/nan.json")
    assert excinfo.value.id is ErrorIds.FETCH_BAD_JSON


def test_default_headers_carry_user_agent(feed_dir: pathlib.Path) -> None:
    capture: list[dict[str, str]] = []
    with serve(feed_dir, capture) as base:
        Fetcher().get_json(base + "/gbfs.json")
    assert _headers_for(capture, "/gbfs.json")["User-Agent"] == USER_AGENT
    assert USER_AGENT.startswith("veodyn gbfs-validator/")


def test_bearer_auth_sends_header_and_drops_user_agent(feed_dir: pathlib.Path) -> None:
    auth = {"type": "bearer_token", "bearerToken": {"token": "tok"}}
    capture: list[dict[str, str]] = []
    with serve(feed_dir, capture) as base:
        Fetcher(auth).get_json(base + "/gbfs.json")
    headers = _headers_for(capture, "/gbfs.json")
    assert headers["Authorization"] == "Bearer tok"
    assert headers.get("User-Agent") != USER_AGENT


def test_basic_auth_uses_lowercase_prefix_and_drops_user_agent(feed_dir: pathlib.Path) -> None:
    """Upstream writes `basic ${base64}` verbatim (gbfs.js:301-307)."""
    auth = {"type": "basic_auth", "basicAuth": {"user": "u", "password": "p"}}
    capture: list[dict[str, str]] = []
    with serve(feed_dir, capture) as base:
        Fetcher(auth).get_json(base + "/gbfs.json")
    headers = _headers_for(capture, "/gbfs.json")
    encoded = base64.b64encode(b"u:p").decode()
    assert headers["Authorization"] == f"basic {encoded}"
    assert headers.get("User-Agent") != USER_AGENT


def test_headers_auth_keeps_user_agent(feed_dir: pathlib.Path) -> None:
    auth = {
        "type": "headers",
        "headers": [
            {"key": "X-Api-Key", "value": "secret"},
            {"key": "X-Empty", "value": ""},
        ],
    }
    capture: list[dict[str, str]] = []
    with serve(feed_dir, capture) as base:
        Fetcher(auth).get_json(base + "/gbfs.json")
    headers = _headers_for(capture, "/gbfs.json")
    assert headers["X-Api-Key"] == "secret"
    assert headers["User-Agent"] == USER_AGENT
    assert "X-Empty" not in headers


def test_unknown_auth_type_keeps_default_headers(feed_dir: pathlib.Path) -> None:
    capture: list[dict[str, str]] = []
    with serve(feed_dir, capture) as base:
        Fetcher({"type": "nonsense"}).get_json(base + "/gbfs.json")
    assert _headers_for(capture, "/gbfs.json")["User-Agent"] == USER_AGENT


@contextlib.contextmanager
def _token_server(payload: bytes, status: int = 200) -> Iterator[tuple[str, list[dict[str, str]]]]:
    seen: list[dict[str, str]] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # pyright: ignore[reportImplicitOverride]  # noqa: A002
            pass

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            seen.append(
                {
                    "body": self.rfile.read(length).decode(),
                    **dict(self.headers.items()),
                }
            )
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/token", seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _oauth_auth(token_url: str) -> dict[str, Any]:
    return {
        "type": "oauth_client_credentials_grant",
        "oauthClientCredentialsGrant": {"user": "u", "password": "p", "tokenUrl": token_url},
    }


def test_prime_oauth_posts_grant_and_stores_bearer(feed_dir: pathlib.Path) -> None:
    with _token_server(b'{"access_token": "abc"}') as (token_url, seen):
        fetcher = Fetcher(_oauth_auth(token_url))
        fetcher.prime_oauth()
    assert seen[0]["body"] == "grant_type=client_credentials"
    assert seen[0]["Content-Type"] == "application/x-www-form-urlencoded"
    assert seen[0]["Authorization"] == f"Basic {base64.b64encode(b'u:p').decode()}"

    capture: list[dict[str, str]] = []
    with serve(feed_dir, capture) as base:
        fetcher.get_json(base + "/gbfs.json")
    headers = _headers_for(capture, "/gbfs.json")
    assert headers["Authorization"] == "Bearer abc"
    assert headers.get("User-Agent") != USER_AGENT


def test_prime_oauth_failure_raises_auth_error() -> None:
    with _token_server(b"{}", status=401) as (url, _seen), pytest.raises(FetchError) as excinfo:
        Fetcher(_oauth_auth(url)).prime_oauth()
    assert excinfo.value.id is ErrorIds.FETCH_AUTH_FAILED


def test_prime_oauth_mirrors_upstreams_bearer_undefined(feed_dir: pathlib.Path) -> None:
    """Upstream does no presence check, so a token-less response sends `Bearer undefined`."""
    with _token_server(b'{"nope": 1}') as (token_url, _seen):
        fetcher = Fetcher(_oauth_auth(token_url))
        fetcher.prime_oauth()
    capture: list[dict[str, str]] = []
    with serve(feed_dir, capture) as base:
        fetcher.get_json(base + "/gbfs.json")
    assert _headers_for(capture, "/gbfs.json")["Authorization"] == "Bearer undefined"


def test_prime_oauth_mirrors_bearer_null_for_an_explicit_null_token() -> None:
    with _token_server(b'{"access_token": null}') as (token_url, _seen):
        fetcher = Fetcher(_oauth_auth(token_url))
        fetcher.prime_oauth()
    assert fetcher.headers["Authorization"] == "Bearer null"


def test_prime_oauth_with_unparseable_body_raises_auth_error() -> None:
    with _token_server(b"not json") as (token_url, _seen), pytest.raises(FetchError) as excinfo:
        Fetcher(_oauth_auth(token_url)).prime_oauth()
    assert excinfo.value.id is ErrorIds.FETCH_AUTH_FAILED


def test_prime_oauth_is_a_noop_for_other_auth_modes(feed_dir: pathlib.Path) -> None:
    fetcher = Fetcher({"type": "bearer_token", "bearerToken": {"token": "tok"}})
    fetcher.prime_oauth()
    capture: list[dict[str, str]] = []
    with serve(feed_dir, capture) as base:
        fetcher.get_json(base + "/gbfs.json")
    assert _headers_for(capture, "/gbfs.json")["Authorization"] == "Bearer tok"
