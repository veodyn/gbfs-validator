"""JavaScript truthiness.

The orchestrator is a port of JS that tests values with `if (x)` all over, and
the two languages disagree on empty containers: `[]` and `{}` are truthy in
JavaScript and falsy in Python.
"""

from __future__ import annotations

from typing import Any


def truthy(value: Any) -> bool:
    if isinstance(value, (list, dict)):
        return True
    return bool(value)
