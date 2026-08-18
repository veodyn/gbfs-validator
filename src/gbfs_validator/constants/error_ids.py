"""Central error ID registry. See guides/error-id-registry.md in agent-starter.

Rules:
  1. Never reuse a retired ID: mark it `# retired` and leave it in place.
  2. One ID per distinct cause, not per raise site.
  3. Numbers are stable; append, never renumber.

Raise via AppError(ErrorIds.X, "...", {...}). Log lines include the ID so
grep, telemetry, and agents can all find every occurrence with one search.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any


class ErrorIds(StrEnum):
    # Fetching a feed file (network, status, decode)
    FETCH_UNREACHABLE = "E_FETCH_001"
    FETCH_BAD_STATUS = "E_FETCH_002"
    FETCH_BAD_JSON = "E_FETCH_003"
    FETCH_AUTH_FAILED = "E_FETCH_004"

    # Schema handling
    SCHEMA_UNKNOWN_VERSION = "E_SCHEMA_001"
    SCHEMA_MISSING_FILE = "E_SCHEMA_002"
    SCHEMA_PATCH_SOURCE_MISMATCH = "E_SCHEMA_003"
    SCHEMA_UNSUPPORTED_PATCH_OP = "E_SCHEMA_004"

    # Feed structure encountered before validation could report on it. These
    # mirror upstream crashes on purpose; see the spec's parity contract.
    FEED_MISSING_URL = "E_FEED_001"
    FEED_MALFORMED_CONTAINER = "E_FEED_002"

    # CLI usage
    CLI_NO_OUTPUT_REQUESTED = "E_CLI_001"


class AppError(Exception):
    """Base error: every raise carries a stable ID plus structured context."""

    def __init__(
        self,
        error_id: ErrorIds,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.id = error_id
        self.context = context or {}

    def to_log_line(self) -> str:
        ctx = " ".join(f"{k}={json.dumps(v, default=str)}" for k, v in self.context.items())
        return f"[{self.id}] {self}{' ' + ctx if ctx else ''}"
