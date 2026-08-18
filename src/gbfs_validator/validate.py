"""Port of upstream's validate.js: patch the schema, validate, filter.

`$patch` and `$merge` come from the partial generators; the errors those
keywords and `if` produce are structural noise that upstream drops before
reporting, so we drop them too.
"""

from __future__ import annotations

import copy
from typing import Any

from gbfs_validator.schema.engine import validate_schema
from gbfs_validator.schema.patching import apply_json_patch, apply_merge_patch

_FILTERED_KEYWORDS = ("$patch", "$merge", "if")


def validate_file(
    schema: dict[str, Any],
    data: object,
    add_schema: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    document = copy.deepcopy(schema)
    for add in add_schema or []:
        if "$patch" in add:
            _check_source(add["$patch"]["source"]["$ref"], document, "patch")
            document = apply_json_patch(document, add["$patch"]["with"])
        if "$merge" in add:
            _check_source(add["$merge"]["source"]["$ref"], document, "merge")
            document = apply_merge_patch(document, add["$merge"]["with"])

    errors = [e for e in validate_schema(document, data) if e["keyword"] not in _FILTERED_KEYWORDS]
    return {"schema": document, "errors": errors or False}


def _check_source(ref: str, document: dict[str, Any], kind: str) -> None:
    if ref != document.get("$id"):
        raise ValueError(
            f"Source of {kind} ({ref}) is not the same as the document ({document.get('$id')})"
        )
