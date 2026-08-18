"""JSON Patch (RFC 6902) and JSON Merge Patch (RFC 7386).

Only the operations the partial generators emit are supported; anything else
raises rather than silently doing nothing.
"""

from __future__ import annotations

import copy
from typing import Any

from gbfs_validator.constants.error_ids import AppError, ErrorIds


def _unescape(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _tokens(path: str) -> list[str]:
    if not path:
        return []
    return [_unescape(t) for t in path.lstrip("/").split("/")]


def _resolve(doc: Any, tokens: list[str]) -> Any:
    node = doc
    for token in tokens:
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def apply_json_patch(doc: dict[str, Any], ops: list[dict[str, Any]]) -> dict[str, Any]:
    patched = copy.deepcopy(doc)
    for op in ops:
        tokens = _tokens(op["path"])
        parent = _resolve(patched, tokens[:-1])
        last = tokens[-1]
        name = op["op"]
        if name == "add":
            _add(parent, last, op["value"])
        elif name == "replace":
            parent[int(last) if isinstance(parent, list) else last] = op["value"]
        elif name == "remove":
            del parent[int(last) if isinstance(parent, list) else last]
        else:
            raise AppError(
                ErrorIds.SCHEMA_UNSUPPORTED_PATCH_OP,
                f"unsupported JSON Patch op {name}",
                {"op": name, "path": op["path"]},
            )
    return patched


def _add(parent: Any, last: str, value: Any) -> None:
    if isinstance(parent, list):
        parent.insert(len(parent) if last == "-" else int(last), value)
    else:
        parent[last] = value


def apply_merge_patch(doc: Any, patch: Any) -> Any:
    if not isinstance(patch, dict):
        return copy.deepcopy(patch)
    out = dict(doc) if isinstance(doc, dict) else {}
    for key, value in patch.items():
        if value is None:
            out.pop(key, None)
        else:
            out[key] = apply_merge_patch(out.get(key, {}), value)
    return out
