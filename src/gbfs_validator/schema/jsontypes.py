"""JSON type and equality predicates with JavaScript semantics.

Python and JavaScript disagree in three places that matter here: bools are
ints in Python, AJV accepts a zero-fraction float as an integer, and JS
regexes treat `\\w`/`\\d`/`\\b` as ASCII.
"""

from __future__ import annotations

import functools
import re


def is_type(value: object, name: str) -> bool:
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "integer":
        if isinstance(value, bool):
            return False
        return isinstance(value, int) or (isinstance(value, float) and value.is_integer())
    return True


def json_eq(a: object, b: object) -> bool:
    """JSON equality: 1 equals 1.0, but True does not equal 1."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(json_eq(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(json_eq(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return type(a) is type(b) and a == b


@functools.lru_cache(maxsize=512)
def _compile(pattern: str) -> re.Pattern[str]:
    # re.ASCII: JS \w, \d and \b are ASCII-only, Python's default is Unicode.
    return re.compile(_js_dollar(pattern), re.ASCII)


def _js_dollar(pattern: str) -> str:
    """Rewrite `$` to `\\Z`: Python's `$` also matches before a trailing
    newline, JavaScript's (without the m flag) does not."""
    out: list[str] = []
    in_class = False
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\" and i + 1 < len(pattern):
            out.append(pattern[i : i + 2])
            i += 2
            continue
        if ch == "[":
            in_class = True
        elif ch == "]":
            in_class = False
        out.append("\\Z" if ch == "$" and not in_class else ch)
        i += 1
    return "".join(out)


def search(pattern: str, value: str) -> bool:
    return _compile(pattern).search(value) is not None


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
