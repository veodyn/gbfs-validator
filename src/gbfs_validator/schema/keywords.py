"""Assertion keywords: the ones that judge an instance without recursing,
plus the two structural ones that recurse through the `walk` callback.
"""

from __future__ import annotations

from typing import Any, Protocol

from gbfs_validator.schema.errors import error, escape_fragment, escape_pointer
from gbfs_validator.schema.formats import FORMATS
from gbfs_validator.schema.jsontypes import is_number, json_eq, search

Errors = list[dict[str, Any]]


class Walk(Protocol):
    def __call__(
        self, schema: object, instance: object, ipath: str, spath: str, out: Errors
    ) -> None: ...


def scalar_checks(
    schema: dict[str, Any], instance: object, ipath: str, spath: str, out: Errors
) -> None:
    if "enum" in schema and not any(json_eq(instance, v) for v in schema["enum"]):
        out.append(
            error(
                ipath,
                spath + "/enum",
                "enum",
                {"allowedValues": schema["enum"]},
                "must be equal to one of the allowed values",
            )
        )
    if "const" in schema and not json_eq(instance, schema["const"]):
        out.append(
            error(
                ipath,
                spath + "/const",
                "const",
                {"allowedValue": schema["const"]},
                "must be equal to constant",
            )
        )
    if is_number(instance):
        _number_checks(schema, instance, ipath, spath, out)
    if isinstance(instance, str):
        _string_checks(schema, instance, ipath, spath, out)


def _number_checks(
    schema: dict[str, Any], instance: Any, ipath: str, spath: str, out: Errors
) -> None:
    if "minimum" in schema and instance < schema["minimum"]:
        limit = schema["minimum"]
        out.append(
            error(
                ipath,
                spath + "/minimum",
                "minimum",
                {"comparison": ">=", "limit": limit},
                f"must be >= {limit}",
            )
        )
    if "maximum" in schema and instance > schema["maximum"]:
        limit = schema["maximum"]
        out.append(
            error(
                ipath,
                spath + "/maximum",
                "maximum",
                {"comparison": "<=", "limit": limit},
                f"must be <= {limit}",
            )
        )


def _string_checks(
    schema: dict[str, Any], instance: str, ipath: str, spath: str, out: Errors
) -> None:
    if "minLength" in schema and len(instance) < schema["minLength"]:
        limit = schema["minLength"]
        out.append(
            error(
                ipath,
                spath + "/minLength",
                "minLength",
                {"limit": limit},
                f"must NOT have fewer than {limit} characters",
            )
        )
    if "maxLength" in schema and len(instance) > schema["maxLength"]:
        limit = schema["maxLength"]
        out.append(
            error(
                ipath,
                spath + "/maxLength",
                "maxLength",
                {"limit": limit},
                f"must NOT have more than {limit} characters",
            )
        )
    if "pattern" in schema and not search(schema["pattern"], instance):
        pattern = schema["pattern"]
        out.append(
            error(
                ipath,
                spath + "/pattern",
                "pattern",
                {"pattern": pattern},
                f'must match pattern "{pattern}"',
            )
        )
    fmt = schema.get("format")
    if fmt in FORMATS and not FORMATS[fmt](instance):
        out.append(
            error(ipath, spath + "/format", "format", {"format": fmt}, f'must match format "{fmt}"')
        )


def _size_error(
    kind: str, limit: int, word: str, ipath: str, spath: str, fewer: bool
) -> dict[str, Any]:
    direction = "fewer than" if fewer else "more than"
    return error(
        ipath,
        f"{spath}/{kind}",
        kind,
        {"limit": limit},
        f"must NOT have {direction} {limit} {word}",
    )


def object_checks(
    walk: Walk, schema: dict[str, Any], instance: object, ipath: str, spath: str, out: Errors
) -> None:
    if not isinstance(instance, dict):
        return

    for prop in schema.get("required", []):
        if prop not in instance:
            out.append(
                error(
                    ipath,
                    spath + "/required",
                    "required",
                    {"missingProperty": prop},
                    f"must have required property '{prop}'",
                )
            )
    if "minProperties" in schema and len(instance) < schema["minProperties"]:
        out.append(
            _size_error("minProperties", schema["minProperties"], "properties", ipath, spath, True)
        )
    if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
        out.append(
            _size_error("maxProperties", schema["maxProperties"], "properties", ipath, spath, False)
        )

    _property_checks(walk, schema, instance, ipath, spath, out)


def _property_checks(
    walk: Walk,
    schema: dict[str, Any],
    instance: dict[str, Any],
    ipath: str,
    spath: str,
    out: Errors,
) -> None:
    props = schema.get("properties", {})
    patterns = schema.get("patternProperties", {})
    has_additional = "additionalProperties" in schema

    for key, value in instance.items():
        kpath = ipath + "/" + escape_pointer(key)
        matched = False
        if key in props:
            matched = True
            walk(props[key], value, kpath, spath + "/properties/" + escape_fragment(key), out)
        for pat, sub in patterns.items():
            if search(pat, key):
                matched = True
                walk(sub, value, kpath, spath + "/patternProperties/" + escape_fragment(pat), out)
        if matched or not has_additional:
            continue
        additional = schema["additionalProperties"]
        if additional is False:
            out.append(
                error(
                    ipath,
                    spath + "/additionalProperties",
                    "additionalProperties",
                    {"additionalProperty": key},
                    "must NOT have additional properties",
                )
            )
        elif additional is not True:
            walk(additional, value, kpath, spath + "/additionalProperties", out)


def array_checks(
    walk: Walk, schema: dict[str, Any], instance: object, ipath: str, spath: str, out: Errors
) -> None:
    if not isinstance(instance, list):
        return

    if "minItems" in schema and len(instance) < schema["minItems"]:
        out.append(_size_error("minItems", schema["minItems"], "items", ipath, spath, True))
    if "maxItems" in schema and len(instance) > schema["maxItems"]:
        out.append(_size_error("maxItems", schema["maxItems"], "items", ipath, spath, False))

    items = schema.get("items")
    if isinstance(items, list):
        _tuple_items(walk, schema, items, instance, ipath, spath, out)
    elif items is not None:
        for i, value in enumerate(instance):
            walk(items, value, f"{ipath}/{i}", spath + "/items", out)


def _tuple_items(
    walk: Walk,
    schema: dict[str, Any],
    items: list[Any],
    instance: list[Any],
    ipath: str,
    spath: str,
    out: Errors,
) -> None:
    for i, sub in enumerate(items):
        if i < len(instance):
            walk(sub, instance[i], f"{ipath}/{i}", f"{spath}/items/{i}", out)
    additional = schema.get("additionalItems")
    if additional is False and len(instance) > len(items):
        out.append(
            error(
                ipath,
                spath + "/additionalItems",
                "additionalItems",
                {"limit": len(items)},
                f"must NOT have more than {len(items)} items",
            )
        )
    elif isinstance(additional, dict):
        for i in range(len(items), len(instance)):
            walk(additional, instance[i], f"{ipath}/{i}", spath + "/additionalItems", out)
