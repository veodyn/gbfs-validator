"""Feed-body readers ported from upstream gbfs.js.

These run before the files they read have been validated, so a malformed
container reaches them as-is. Upstream throws there and so do we: the crash
is the behavior, not a gap. Member access follows JS, where only null and
undefined throw and a boxed primitive answers undefined; calling a method
that is not there throws in both languages.
"""

from __future__ import annotations

import json
from typing import Any

from gbfs_validator.constants.error_ids import AppError, ErrorIds
from gbfs_validator.jstruth import truthy

_SCHEMAS: dict[tuple[str, str], dict[str, Any]] = {}


def load_schema(version: str, file: str) -> dict[str, Any]:
    """The vendored schema for one file of one version, cached."""
    key = (version, file)
    if key not in _SCHEMAS:
        from importlib.resources import files

        path = files("gbfs_validator") / "data" / "schemas" / f"v{version}" / f"{file}.json"
        try:
            _SCHEMAS[key] = json.loads(path.read_text())
        except (FileNotFoundError, NotADirectoryError, OSError) as exc:
            raise AppError(
                ErrorIds.SCHEMA_MISSING_FILE,
                "can not require",
                {"version": version, "file": file},
            ) from exc
    return _SCHEMAS[key]


def _chain(value: Any, key: str) -> Any:
    """`value?.key`: None when value cannot carry properties."""
    return value.get(key) if isinstance(value, dict) else None


def _iterable(value: Any, what: str) -> list[Any]:
    """`value.map(...)` / `value.some(...)`: anything else throws in JS."""
    if not isinstance(value, list):
        raise AppError(
            ErrorIds.FEED_MALFORMED_CONTAINER,
            f"{what} is not an array",
            {"got": type(value).__name__},
        )
    return value


def prop(value: Any, key: str, what: str) -> Any:
    """`value.key`: undefined on a boxed primitive, a throw on null/undefined."""
    if isinstance(value, dict):
        return value.get(key)
    if value is None:
        raise AppError(
            ErrorIds.FEED_MALFORMED_CONTAINER,
            f"cannot read {key} of {what}",
            {"got": "null"},
        )
    return None


def get_vehicle_types(file: dict[str, Any]) -> list[dict[str, Any]]:
    body = file.get("body")
    if isinstance(body, list):
        found: list[dict[str, Any]] = []
        for language in body:
            data = _chain(prop(language, "body", "language"), "data")
            if data is None:
                continue
            for vehicle_type in _iterable(prop(data, "vehicle_types", "data"), "vehicle_types"):
                if not any(
                    f["vehicle_type_id"] == prop(vehicle_type, "vehicle_type_id", "vehicle type")
                    for f in found
                ):
                    found.append(_vehicle_type(vehicle_type))
        return found
    data = _chain(body, "data")
    if data is None:
        return []
    return [
        _vehicle_type(vt) for vt in _iterable(prop(data, "vehicle_types", "data"), "vehicle_types")
    ]


def _vehicle_type(vehicle_type: Any) -> dict[str, Any]:
    return {
        "vehicle_type_id": prop(vehicle_type, "vehicle_type_id", "vehicle type"),
        "form_factor": prop(vehicle_type, "form_factor", "vehicle type"),
        "propulsion_type": prop(vehicle_type, "propulsion_type", "vehicle type"),
    }


def get_pricing_plans(file: dict[str, Any]) -> list[dict[str, Any]] | None:
    body = file.get("body")
    if isinstance(body, list):
        found: list[dict[str, Any]] = []
        for language in body:
            data = _chain(prop(language, "body", "language"), "data")
            if data is None:
                continue
            for plan in _iterable(prop(data, "plans", "data"), "plans"):
                plan_id = prop(plan, "plan_id", "pricing plan")
                if not any(prop(f, "plan_id", "pricing plan") == plan_id for f in found):
                    found.append(plan)
        return found
    data = _chain(body, "data")
    return None if data is None else prop(data, "plans", "data")


def had_vehicle_type_id(file: dict[str, Any]) -> bool:
    return _any_vehicle(file, "bikes", lambda b: truthy(prop(b, "vehicle_type_id", "vehicle")))


def has_pricing_plan_id(file: dict[str, Any]) -> bool:
    return _any_vehicle(file, "bikes", lambda b: truthy(prop(b, "pricing_plan_id", "vehicle")))


def has_rental_uris(file: dict[str, Any], key: str, store: str) -> bool:
    def has_store(entry: Any) -> bool:
        return truthy(_chain(prop(entry, "rental_uris", "vehicle"), store))

    return _any_vehicle(file, key, has_store)


def _any_vehicle(file: dict[str, Any], key: str, predicate: Any) -> bool:
    """`body.data[key].some(predicate)`, with no optional chaining anywhere."""
    body = file.get("body")
    if isinstance(body, list):
        return any(
            any(predicate(entry) for entry in _entries(prop(language, "body", "language"), key))
            for language in body
        )
    return any(predicate(entry) for entry in _entries(body, key))


def _entries(body: Any, key: str) -> list[Any]:
    data = prop(body, "data", "body")
    return _iterable(prop(data, key, "data"), key)


def file_exist(file: dict[str, Any] | None) -> bool:
    if not file:
        return False
    if file.get("exists"):
        return True
    body = file.get("body")
    if isinstance(body, list):
        return any(language.get("exists") for language in body)
    return False


def is_js_object(body: Any) -> bool:
    """`typeof body === "object"`, which is also true of null and arrays."""
    return isinstance(body, (dict, list)) or body is None


def find_feed(value: Any, file_type: str) -> dict[str, Any] | None:
    """`data[lang].feeds.find(...)`, which throws when feeds is not an array."""
    for feed in _iterable(prop(value, "feeds", "language entry"), "feeds"):
        if prop(feed, "name", "feed entry") == file_type:
            return feed
    return None
