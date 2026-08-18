"""A draft-07 JSON Schema validator scoped to what the GBFS schemas use.

It emits AJV-shaped errors and collects all of them (AJV's allErrors mode),
because reports are compared against upstream's AJV output. Keyword coverage
is deliberately partial: everything the pinned schemas and the partial
generators use, and nothing else.
"""

from __future__ import annotations

from typing import Any

from gbfs_validator.schema.applicators import APPLICATORS, apply_error_message
from gbfs_validator.schema.errors import error
from gbfs_validator.schema.jsontypes import is_type
from gbfs_validator.schema.keywords import Errors, array_checks, object_checks, scalar_checks


def validate_schema(schema: dict[str, Any], instance: object) -> Errors:
    out: Errors = []
    _walk(schema, instance, "", "#", out)
    return out


def _walk(schema: object, instance: object, ipath: str, spath: str, out: Errors) -> None:
    if schema is True:
        return
    if schema is False:
        out.append(
            error(ipath, spath + "/false schema", "false schema", {}, "boolean schema is false")
        )
        return
    if not isinstance(schema, dict) or not schema:
        return

    # A failed `type` does not stop the other keywords: AJV keeps going and
    # each keyword family is a no-op on the wrong instance type anyway.
    if "type" in schema:
        _check_type(schema["type"], instance, ipath, spath, out)

    scalar_checks(schema, instance, ipath, spath, out)
    object_checks(_walk, schema, instance, ipath, spath, out)
    array_checks(_walk, schema, instance, ipath, spath, out)

    for name, apply in APPLICATORS.items():
        if name in schema:
            apply(_walk, schema, instance, ipath, spath, out)

    # ajv-errors rewrites errors the keywords above produced, so it runs last.
    if "errorMessage" in schema:
        apply_error_message(schema, ipath, spath, out)


def _check_type(
    declared: str | list[str], instance: object, ipath: str, spath: str, out: Errors
) -> None:
    names: list[str] = declared if isinstance(declared, list) else [declared]
    if any(is_type(instance, n) for n in names):
        return
    # AJV keeps the declared value in params but joins it for the message.
    out.append(
        error(ipath, spath + "/type", "type", {"type": declared}, f"must be {','.join(names)}")
    )
