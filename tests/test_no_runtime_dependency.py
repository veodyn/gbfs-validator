"""The zero-dependency promise, enforced rather than asserted in prose."""

from __future__ import annotations

import ast
import pathlib
import sys

SRC = pathlib.Path(__file__).resolve().parent.parent / "src/gbfs_validator"


def _imported_roots(tree: ast.Module) -> list[str]:
    roots: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots += [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.append(node.module.split(".")[0])
    return roots


def test_only_stdlib_imports() -> None:
    stdlib = sys.stdlib_module_names
    for py in sorted(SRC.rglob("*.py")):
        tree = ast.parse(py.read_text())
        for root in _imported_roots(tree):
            assert root == "gbfs_validator" or root in stdlib, f"{py}: {root}"


def test_declares_no_dependencies() -> None:
    pyproject = (SRC.parent.parent / "pyproject.toml").read_text()
    assert "dependencies = []" in pyproject
