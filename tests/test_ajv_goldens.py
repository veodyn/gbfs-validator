"""The engine's oracle: every case run through upstream's own AJV stack.

If Python and a golden disagree, the golden is right.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from gbfs_validator.validate import validate_file

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIX = ROOT / "tests/fixtures/ajv"
SCHEMAS = ROOT / "src/gbfs_validator/data/schemas"

CASES = {c["name"]: c for c in json.loads((FIX / "cases.json").read_text())}
GOLDENS = json.loads((FIX / "goldens.json").read_text())


def _key(err: dict) -> tuple[str, str, str, str]:
    return (
        err["instancePath"],
        err["schemaPath"],
        err["keyword"],
        json.dumps(err["params"], sort_keys=True),
    )


def normalize(errors) -> list[tuple[str, str, str, str]]:
    if not errors:
        return []
    return sorted(_key(e) for e in errors)


def _run(case: dict):
    schema = (
        json.loads((SCHEMAS / case["schemaFile"]).read_text())
        if "schemaFile" in case
        else case["schema"]
    )
    return validate_file(schema, case["data"], case.get("addSchema"))["errors"]


@pytest.mark.parametrize("name", sorted(GOLDENS))
def test_engine_matches_ajv_golden(name: str) -> None:
    expected = GOLDENS[name]
    assert not isinstance(expected, dict), f"{name}: oracle threw, case is unusable"
    assert normalize(_run(CASES[name])) == normalize(expected)


def test_every_case_has_a_golden() -> None:
    assert set(CASES) == set(GOLDENS)


def test_goldens_are_not_all_empty() -> None:
    with_errors = [name for name, errs in GOLDENS.items() if errs]
    assert len(with_errors) > 40
