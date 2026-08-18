"""The corpus, checked against upstream's recorded verdict, without Node.

`tools/differential.py` is the live parity gate and needs the upstream clone.
`expectations.json` is a snapshot of what upstream said about each feed,
written by `tools/differential.py --write-expectations`, so plain CI checks
the same parity contract offline. If a feed's expectation changes, upstream's
behavior changed, and that belongs in a commit of its own.
"""

from __future__ import annotations

import contextlib
import json
import pathlib
import sys

import pytest

from fixtureserver import serve
from gbfs_validator import GBFS

ROOT = pathlib.Path(__file__).resolve().parent.parent
FEEDS = ROOT / "tests/fixtures/feeds"
FEED_DIRS = sorted(p for p in FEEDS.iterdir() if p.is_dir())
EXPECTATIONS = json.loads((FEEDS / "expectations.json").read_text())

sys.path.insert(0, str(ROOT / "tools"))
from differential import normalize  # noqa: E402


@contextlib.contextmanager
def running(feed_dir: pathlib.Path):
    """Yield a validator while its feed is still being served."""
    meta = json.loads((feed_dir / "meta.json").read_text())
    options = meta.get("options") or {}
    with serve(feed_dir) as base:
        yield GBFS(
            base + meta.get("path", "/gbfs.json"),
            docked=bool(options.get("docked")),
            freefloating=bool(options.get("freefloating")),
            version=options.get("version"),
        )


def as_json(value: object) -> object:
    """Round-trip so tuples compare equal to the lists JSON gave us back."""
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def our_outcome(feed_dir: pathlib.Path) -> object:
    with running(feed_dir) as gbfs:
        try:
            outcome = normalize({"report": gbfs.validation()})
        except Exception as exc:  # noqa: BLE001 - a crash is a valid outcome
            outcome = normalize({"critical": True, "why": str(exc)})
    return as_json(outcome)


@pytest.mark.parametrize("feed_dir", FEED_DIRS, ids=lambda p: p.name)
def test_our_report_matches_upstreams_recorded_verdict(feed_dir: pathlib.Path) -> None:
    assert feed_dir.name in EXPECTATIONS, "run tools/differential.py --write-expectations"
    assert our_outcome(feed_dir) == EXPECTATIONS[feed_dir.name]


def test_every_feed_has_an_expectation_and_no_strays() -> None:
    assert {p.name for p in FEED_DIRS} == set(EXPECTATIONS)


@pytest.mark.parametrize("feed_dir", FEED_DIRS, ids=lambda p: p.name)
def test_every_feed_declares_its_options(feed_dir: pathlib.Path) -> None:
    meta = json.loads((feed_dir / "meta.json").read_text())
    assert set(meta.get("options", {})) == {"docked", "freefloating", "version"}


def test_the_corpus_covers_every_known_version() -> None:
    """Every version in the table needs at least one feed declaring it."""
    from gbfs_validator.versions import KNOWN_VERSIONS

    declared: set[str] = set()
    for feed_dir in FEED_DIRS:
        discovery = feed_dir / "gbfs.json"
        if not discovery.is_file():
            continue  # the no-autodiscovery feed has no discovery document
        gbfs = json.loads(discovery.read_text() or "null")
        if isinstance(gbfs, dict) and "version" in gbfs:
            declared.add(str(gbfs["version"]))
    assert set(KNOWN_VERSIONS) - declared == set()


def test_the_corpus_exercises_both_crashing_and_reporting() -> None:
    outcomes = list(EXPECTATIONS.values())
    assert sum(1 for o in outcomes if o.get("critical")) >= 3
    assert sum(1 for o in outcomes if "files" in o) >= 15
