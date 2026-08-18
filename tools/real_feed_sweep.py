"""Differential sweep over real published GBFS feeds.

The fixture corpus is built from cases we thought of. This samples feeds from
MobilityData's own systems catalog and compares both validators on them, which
is the check that finds what nobody thought of.

Live feeds move: vehicle positions change between two sequential fetches, and
comparing across that produces false differences. So each feed is snapshotted
to a temporary directory first and both validators run against the snapshot.

Not part of CI: it needs the network and the catalog changes under us.

    python tools/real_feed_sweep.py [--sample N] [--seed N]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import pathlib
import random
import sys
import tempfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "tools")]

import differential as diff  # noqa: E402

from fixtureserver import serve  # noqa: E402

CATALOG = "https://raw.githubusercontent.com/MobilityData/gbfs/master/systems.csv"


def catalog() -> list[dict[str, str]]:
    raw = urllib.request.urlopen(CATALOG, timeout=60).read().decode("utf-8-sig")
    return [
        row
        for row in csv.DictReader(io.StringIO(raw))
        if row.get("Auto-Discovery URL", "").startswith("http")
        and not (row.get("Authentication Info URL") or "").strip()
    ]


def pick(rows: list[dict[str, str]], sample: int, seed: int) -> list[dict[str, str]]:
    """Spread the sample across declared versions rather than taking the head."""
    by_version: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        for version in (row.get("Supported Versions") or "unknown").split(";"):
            by_version.setdefault(version.strip() or "unknown", []).append(row)
    rng = random.Random(seed)  # noqa: S311 - sampling a catalog, not crypto
    picked: list[dict[str, str]] = []
    for _, group in sorted(by_version.items()):
        picked += rng.sample(group, min(3, len(group)))
    rng.shuffle(picked)
    return picked[:sample]


def fetch(url: str) -> bytes | None:
    """The catalog is full of dead and moved feeds; say which, and move on."""
    try:
        return urllib.request.urlopen(url, timeout=60).read()
    except Exception as exc:  # noqa: BLE001 - any failure means unusable feed
        print(f"     unreachable {url}: {type(exc).__name__}: {exc}")
        return None


def snapshot(url: str, into: pathlib.Path) -> bool:
    """Freeze a feed and its files so both validators see identical bytes."""
    raw = fetch(url)
    if raw is None:
        return False
    try:
        discovery = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"     not JSON {url}: {exc}")
        return False
    data = discovery.get("data") if isinstance(discovery, dict) else None
    if not isinstance(data, dict):
        print(f"     no data object {url}")
        return False
    blocks = [data] if "feeds" in data else [b for b in data.values() if isinstance(b, dict)]
    for block in blocks:
        kept = []
        for feed in block.get("feeds", []):
            name = feed.get("name")
            body = fetch(feed.get("url", ""))
            if body is None:
                # Upstream sees the same 404, so dropping it keeps them level.
                continue
            (into / f"{name}.json").write_bytes(body)
            kept.append({"name": name, "url": "{BASE}/" + f"{name}.json"})
        block["feeds"] = kept
    (into / "gbfs.json").write_text(json.dumps(discovery))
    (into / "meta.json").write_text('{"options": {}}')
    return True


def sweep(sample: int, seed: int) -> int:
    rows = pick(catalog(), sample, seed)
    agree = differ = skipped = 0
    for row in rows:
        label = f"{row['Name'][:30]:30} {(row.get('Supported Versions') or '?')[:12]:12}"
        with tempfile.TemporaryDirectory() as tmp:
            feed_dir = pathlib.Path(tmp)
            if not snapshot(row["Auto-Discovery URL"].strip(), feed_dir):
                print(f"skip {label} unreachable")
                skipped += 1
                continue
            with serve(feed_dir) as base:
                url = base + "/gbfs.json"
                theirs = diff.normalize(diff.run_upstream(url, {}))
                ours = diff.normalize(diff.run_ours(url, {}))
        if theirs == ours:
            print(f"ok   {label} errors={theirs.get('summary', {}).get('errorsCount')}")
            agree += 1
            continue
        differ += 1
        print(f"DIFF {label}  {row['Auto-Discovery URL']}")
        print("  upstream:", json.dumps(theirs.get("summary"), default=str)[:300])
        print("  ours    :", json.dumps(ours.get("summary"), default=str)[:300])
    print(f"\n{agree} agree, {differ} differ, {skipped} skipped, of {len(rows)} feeds")
    return 1 if differ else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=int, default=24)
    parser.add_argument("--seed", type=int, default=20260818)
    args = parser.parse_args()
    return sweep(args.sample, args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
