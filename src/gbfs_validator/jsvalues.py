"""JavaScript value semantics the orchestrator reads unvalidated feeds with.

`x.k` throws only when `x` is null or undefined; on a number, string or boolean
it is undefined, and calling a method that is not there throws instead.
`Object.entries` accepts arrays. `${x}` renders 3.0 as "3". Each of those
decides whether a malformed feed crashes or gets a report, so they are mirrored
rather than guarded against.
"""

from __future__ import annotations

from typing import Any

from gbfs_validator.constants.error_ids import AppError, ErrorIds


def member(value: Any, key: str) -> Any:
    """`value.key`, unguarded: undefined for anything that is not an object."""
    if value is None:
        raise AppError(
            ErrorIds.FEED_MALFORMED_CONTAINER,
            f"cannot read properties of null (reading '{key}')",
            {"key": key},
        )
    return value.get(key) if isinstance(value, dict) else None


def optional(value: Any, *keys: str | int) -> Any:
    """`value?.a?.[0]?.b`: a nullish link short-circuits the rest to None."""
    for key in keys:
        if value is None:
            return None
        value = _property(value, key)
    return value


def _property(value: Any, key: str | int) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    if isinstance(value, list) and isinstance(key, int):
        return value[key] if -len(value) <= key < len(value) else None
    return None


def entries(value: Any, what: str) -> list[tuple[str, Any]]:
    """`Object.entries(value)`: arrays index by string, scalars give nothing."""
    if value is None:
        raise AppError(
            ErrorIds.FEED_MALFORMED_CONTAINER,
            f"cannot convert {what} (null) to object",
            {"what": what},
        )
    if isinstance(value, dict):
        return [(str(key), item) for key, item in value.items()]
    if isinstance(value, (list, str)):
        return [(str(index), item) for index, item in enumerate(value)]
    return []


def array(value: Any, what: str) -> list[Any]:
    """`value.find(...)` / `value.filter(...)`: only arrays carry them."""
    if isinstance(value, list):
        return value
    raise AppError(
        ErrorIds.FEED_MALFORMED_CONTAINER,
        f"{what} is not a function",
        {"got": type(value).__name__},
    )


def interpolate(value: Any) -> str:
    """`${value}`, which is how upstream builds every schema and version path."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    if value is None:
        return "null"
    return str(value)
