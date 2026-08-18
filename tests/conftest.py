"""Shared fixtures: minimal 2.3 feeds served over HTTP, clean and with errors."""

from __future__ import annotations

import dataclasses
import json
import pathlib
from collections.abc import Iterator

import pytest

from fixtureserver import serve

V23 = {"last_updated": 1566224400, "ttl": 0, "version": "2.3"}


@dataclasses.dataclass
class Feed:
    """A served fixture feed: `base` is the URL to hand the CLI."""

    base: str
    path: pathlib.Path


def system_information(name: object = "S") -> dict[str, object]:
    return {
        **V23,
        "data": {"system_id": "s", "language": "en", "name": name, "timezone": "Etc/UTC"},
    }


def discovery(url_prefix: str) -> dict[str, object]:
    feeds = [{"name": "system_information", "url": f"{url_prefix}/system_information.json"}]
    return {**V23, "data": {"en": {"feeds": feeds}}}


def write_feed(directory: pathlib.Path, url_prefix: str, name: object = "S") -> pathlib.Path:
    (directory / "gbfs.json").write_text(json.dumps(discovery(url_prefix)))
    (directory / "system_information.json").write_text(json.dumps(system_information(name)))
    return directory


@pytest.fixture
def tmp_feed(tmp_path: pathlib.Path) -> Iterator[Feed]:
    write_feed(tmp_path, "{BASE}")
    with serve(tmp_path) as base:
        yield Feed(base=base, path=tmp_path)


@pytest.fixture
def tmp_feed_with_errors(tmp_path: pathlib.Path) -> Iterator[Feed]:
    write_feed(tmp_path, "{BASE}", name=42)
    with serve(tmp_path) as base:
        yield Feed(base=base, path=tmp_path)
