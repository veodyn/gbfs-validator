"""urllib fetcher for GBFS files: http(s) and file URLs, upstream's four auth modes."""

from __future__ import annotations

import base64
import http.client
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from gbfs_validator.constants.error_ids import AppError, ErrorIds
from gbfs_validator.version import __version__

USER_AGENT = (
    f"veodyn gbfs-validator/{__version__} "
    f"(Python {sys.version_info.major}.{sys.version_info.minor})"
)


class FetchError(AppError):
    """Any failure to turn a URL into JSON: network, status >= 400, or decode."""

    def __init__(
        self,
        url: str,
        message: str,
        error_id: ErrorIds = ErrorIds.FETCH_UNREACHABLE,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(error_id, message, {"url": url, **(context or {})})
        self.url = url


class _Undefined:
    """Stands in for a JSON key that is absent rather than null."""


_UNDEFINED = _Undefined()


def _js_interpolate(value: Any) -> str:
    """Render a decoded JSON value the way a JS template literal would."""
    if isinstance(value, _Undefined):
        return "undefined"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _reject_constant(name: str) -> Any:
    # JS JSON.parse rejects NaN/Infinity; Python's json accepts them by default.
    raise ValueError(f"invalid JSON literal: {name}")


def _basic_credentials(user: str, password: str) -> str:
    return base64.b64encode(f"{user}:{password}".encode()).decode()


def _build_headers(auth: dict[str, Any] | None) -> dict[str, str]:
    """Port of the gbfs.js constructor, header-replacement quirk included."""
    headers = {"User-Agent": USER_AGENT}
    if not auth or not auth.get("type"):
        return headers
    kind = auth["type"]
    if kind == "basic_auth" and auth.get("basicAuth"):
        credentials = auth["basicAuth"]
        # Upstream writes the lowercase literal `basic ` (gbfs.js:302).
        encoded = _basic_credentials(credentials.get("user", ""), credentials.get("password", ""))
        return {"Authorization": f"basic {encoded}"}
    if kind == "bearer_token" and auth.get("bearerToken"):
        return {"Authorization": f"Bearer {auth['bearerToken'].get('token', '')}"}
    if kind == "headers":
        for header in auth.get("headers") or []:
            if header and header.get("value"):
                headers[header["key"]] = header["value"]
    return headers


class Fetcher:
    """Fetches and decodes JSON, carrying one feed's auth for every request."""

    def __init__(self, auth: dict[str, Any] | None = None, timeout: float = 30.0) -> None:
        self.auth = auth
        self.timeout = timeout
        self.headers = _build_headers(auth)

    def get_json(self, url: str) -> object:
        raw = self._read(url)
        try:
            return json.loads(raw, parse_constant=_reject_constant)
        except (ValueError, UnicodeDecodeError) as exc:
            raise FetchError(url, f"invalid JSON at {url}: {exc}", ErrorIds.FETCH_BAD_JSON) from exc

    def prime_oauth(self) -> None:
        """POST the client-credentials grant, then replace headers with the bearer token."""
        auth = self.auth or {}
        if auth.get("type") != "oauth_client_credentials_grant":
            return
        grant = auth.get("oauthClientCredentialsGrant") or {}
        token_url = grant.get("tokenUrl") or ""
        if not token_url:
            raise FetchError(token_url, "oauth grant has no tokenUrl", ErrorIds.FETCH_AUTH_FAILED)
        request = urllib.request.Request(
            token_url,
            data=b"grant_type=client_credentials",
            headers={
                "Authorization": (
                    f"Basic {_basic_credentials(grant.get('user', ''), grant.get('password', ''))}"
                ),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read(), parse_constant=_reject_constant)
        except (http.client.HTTPException, OSError, ValueError) as exc:
            raise FetchError(
                token_url, f"oauth token request failed: {exc}", ErrorIds.FETCH_AUTH_FAILED
            ) from exc
        token = payload.get("access_token", _UNDEFINED) if isinstance(payload, dict) else _UNDEFINED
        # Upstream never checks for the token, so a response without one sends
        # the literal `Bearer undefined` and lets the feed files 401 (gbfs.js:596-599).
        self.headers = {"Authorization": f"Bearer {_js_interpolate(token)}"}

    def _read(self, url: str) -> bytes:
        try:
            # Request() parses the URL, so a malformed one must fail in here too.
            scheme = urllib.parse.urlsplit(url).scheme
            request = (
                urllib.request.Request(url)
                if scheme == "file"
                else urllib.request.Request(url, headers=self.headers)
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise FetchError(
                url, f"{url} returned HTTP {exc.code}", ErrorIds.FETCH_BAD_STATUS
            ) from exc
        except (http.client.HTTPException, OSError, ValueError) as exc:
            raise FetchError(url, f"could not fetch {url}: {exc}") from exc
