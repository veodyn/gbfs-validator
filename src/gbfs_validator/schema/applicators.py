"""Applicator keywords: the ones that judge an instance by running
subschemas against it. Each takes the engine's `walk` so recursion stays in
one place.
"""

from __future__ import annotations

from typing import Any

from gbfs_validator.schema.errors import error, escape_fragment
from gbfs_validator.schema.keywords import Errors, Walk


def apply_allof(
    walk: Walk, schema: dict[str, Any], instance: object, ipath: str, spath: str, out: Errors
) -> None:
    for i, sub in enumerate(schema["allOf"]):
        walk(sub, instance, ipath, f"{spath}/allOf/{i}", out)


def apply_anyof(
    walk: Walk, schema: dict[str, Any], instance: object, ipath: str, spath: str, out: Errors
) -> None:
    branch_errors: Errors = []
    for i, sub in enumerate(schema["anyOf"]):
        errs: Errors = []
        walk(sub, instance, ipath, f"{spath}/anyOf/{i}", errs)
        if not errs:
            return
        branch_errors.extend(errs)
    out.extend(branch_errors)
    out.append(error(ipath, spath + "/anyOf", "anyOf", {}, "must match a schema in anyOf"))


def apply_oneof(
    walk: Walk, schema: dict[str, Any], instance: object, ipath: str, spath: str, out: Errors
) -> None:
    passing: list[int] = []
    branch_errors: Errors = []
    for i, sub in enumerate(schema["oneOf"]):
        errs: Errors = []
        walk(sub, instance, ipath, f"{spath}/oneOf/{i}", errs)
        if errs:
            branch_errors.extend(errs)
        else:
            passing.append(i)
    if len(passing) == 1:
        return
    if not passing:
        out.extend(branch_errors)
    out.append(
        error(
            ipath,
            spath + "/oneOf",
            "oneOf",
            {"passingSchemas": passing or None},
            "must match exactly one schema in oneOf",
        )
    )


def apply_not(
    walk: Walk, schema: dict[str, Any], instance: object, ipath: str, spath: str, out: Errors
) -> None:
    errs: Errors = []
    walk(schema["not"], instance, ipath, spath + "/not", errs)
    if not errs:
        out.append(error(ipath, spath + "/not", "not", {}, "must NOT be valid"))


def apply_if(
    walk: Walk, schema: dict[str, Any], instance: object, ipath: str, spath: str, out: Errors
) -> None:
    condition: Errors = []
    walk(schema["if"], instance, ipath, spath + "/if", condition)
    branch = "then" if not condition else "else"
    if branch not in schema:
        return
    errs: Errors = []
    walk(schema[branch], instance, ipath, f"{spath}/{branch}", errs)
    if errs:
        out.extend(errs)
        out.append(
            error(
                ipath,
                spath + "/if",
                "if",
                {"failingKeyword": branch},
                f'must match "{branch}" schema',
            )
        )


def apply_dependencies(
    walk: Walk, schema: dict[str, Any], instance: object, ipath: str, spath: str, out: Errors
) -> None:
    if not isinstance(instance, dict):
        return
    for prop, dep in schema["dependencies"].items():
        if prop not in instance:
            continue
        if isinstance(dep, list):
            _missing_deps(prop, dep, instance, ipath, spath, out)
        else:
            walk(dep, instance, ipath, f"{spath}/dependencies/{escape_fragment(prop)}", out)


def _missing_deps(
    prop: str,
    dep: list[str],
    instance: dict[str, Any],
    ipath: str,
    spath: str,
    out: Errors,
) -> None:
    for missing in dep:
        if missing in instance:
            continue
        out.append(
            error(
                ipath,
                spath + "/dependencies",
                "dependencies",
                {
                    "property": prop,
                    "missingProperty": missing,
                    "depsCount": len(dep),
                    "deps": ", ".join(dep),
                },
                f"must have property {missing} when property {prop} is present",
            )
        )


def apply_contains(
    walk: Walk, schema: dict[str, Any], instance: object, ipath: str, spath: str, out: Errors
) -> None:
    if not isinstance(instance, list):
        return
    item_errors: Errors = []
    for i, value in enumerate(instance):
        errs: Errors = []
        walk(schema["contains"], value, f"{ipath}/{i}", spath + "/contains", errs)
        if not errs:
            return
        item_errors.extend(errs)
    out.extend(item_errors)
    out.append(
        error(
            ipath,
            spath + "/contains",
            "contains",
            {"minContains": 1},
            "must contain at least 1 valid item(s)",
        )
    )


def apply_error_message(schema: dict[str, Any], ipath: str, spath: str, out: Errors) -> None:
    """ajv-errors, in its two forms.

    A string replaces every error from this subschema with one message; an
    object with a `required` map replaces only the named required errors.
    """
    message = schema["errorMessage"]
    if isinstance(message, str):
        _collapse_subschema(message, ipath, spath, out)
        return
    if not isinstance(message, dict):
        return
    mapping = message.get("required", {})
    if not mapping:
        return
    kept: Errors = []
    replaced: dict[str, Errors] = {}
    for e in out:
        prop = e["params"].get("missingProperty")
        if _is_local_required(e, ipath, spath) and prop in mapping:
            replaced.setdefault(prop, []).append(e)
        else:
            kept.append(e)
    if not replaced:
        return
    out[:] = kept
    for prop, originals in replaced.items():
        for original in originals:
            # ajv-errors marks the error it consumed rather than dropping it.
            original["emUsed"] = True
        out.append(
            error(
                ipath,
                spath + "/errorMessage",
                "errorMessage",
                {"errors": originals},
                mapping[prop],
            )
        )


def _collapse_subschema(message: str, ipath: str, spath: str, out: Errors) -> None:
    """String form: one message for everything this subschema produced.

    An error a nested errorMessage already customized is left alone, which is
    why the inner message survives when an outer one also matches.
    """
    prefix = spath + "/"
    consumed = [
        e for e in out if e["schemaPath"].startswith(prefix) and e["keyword"] != "errorMessage"
    ]
    if not consumed:
        return
    taken = {id(e) for e in consumed}
    out[:] = [e for e in out if id(e) not in taken]
    for original in consumed:
        original["emUsed"] = True
    out.append(error(ipath, spath + "/errorMessage", "errorMessage", {"errors": consumed}, message))


def _is_local_required(err: dict[str, Any], ipath: str, spath: str) -> bool:
    return (
        err["keyword"] == "required"
        and err["instancePath"] == ipath
        and err["schemaPath"] == spath + "/required"
    )


APPLICATORS = {
    "allOf": apply_allof,
    "anyOf": apply_anyof,
    "oneOf": apply_oneof,
    "not": apply_not,
    "if": apply_if,
    "dependencies": apply_dependencies,
    "contains": apply_contains,
}
