"""AJV-shaped validation error objects.

The five keys and their spelling are AJV's, not ours: reports are compared
against upstream's output, so the shape is part of the contract.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote


def error(
    instance_path: str,
    schema_path: str,
    keyword: str,
    params: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    return {
        "instancePath": instance_path,
        "schemaPath": schema_path,
        "keyword": keyword,
        "params": params,
        "message": message,
    }


def escape_pointer(token: str) -> str:
    """RFC 6901 escaping for one JSON Pointer token."""
    return token.replace("~", "~0").replace("/", "~1")


def escape_fragment(token: str) -> str:
    """AJV's schemaPath escaping: pointer-escape, then encodeURIComponent.

    `safe` spells out the characters encodeURIComponent leaves alone that
    Python's quote would otherwise percent-encode.
    """
    return quote(escape_pointer(token), safe="!*'()")
