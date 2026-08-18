"""Compare our reports against the pinned upstream validator.

Both sides run over the same fixture feed, served from a local HTTP server,
and are reduced to the parity contract in the spec: which notices fire, on
which file occurrence, at which path. Message text and schema echoes are out
of scope; everything else, including crashing rather than reporting, is in.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from fixtureserver import serve  # noqa: E402
from gbfs_validator import GBFS  # noqa: E402

FEEDS = ROOT / "tests/fixtures/feeds"


def canon_params(params: Any) -> str:
    """errorMessage nests the errors it consumed; compare their count only."""
    params = dict(params or {})
    if isinstance(params.get("errors"), list):
        params["errors"] = len(params["errors"])
    return json.dumps(params, sort_keys=True, default=str)


def norm_errors(entry: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    errors = entry.get("errors")
    if not isinstance(errors, list):
        return []
    return sorted(
        (
            e.get("instancePath", ""),
            e.get("schemaPath", ""),
            e.get("keyword", ""),
            canon_params(e.get("params")),
        )
        for e in errors
    )


def norm_file(index: int, file: dict[str, Any]) -> dict[str, Any]:
    # The index keeps duplicate entries apart: a manifest can appear twice,
    # once from the version table and once from the manifest_url chase.
    out: dict[str, Any] = {
        "index": index,
        "file": file.get("file") or f"{file.get('type', '')}.json",
        "required": bool(file.get("required")),
        "exists": bool(file.get("exists")),
        "hasErrors": bool(file.get("hasErrors")),
        "errorsCount": file.get("errorsCount"),
        "errors": norm_errors(file),
    }
    languages = file.get("languages")
    if languages is not None:
        out["languages"] = sorted(
            (str(lang.get("lang", "")), bool(lang.get("exists")), norm_errors(lang))
            for lang in languages
        )
    return out


def normalize(outcome: dict[str, Any]) -> dict[str, Any]:
    if outcome.get("harness_error"):
        return {"harnessError": outcome["harness_error"]}
    if outcome.get("critical"):
        return {"critical": True}
    report = outcome["report"]
    summary = report.get("summary", {})
    out: dict[str, Any] = {
        "summary": {
            "hasErrors": bool(summary.get("hasErrors")),
            "errorsCount": summary.get("errorsCount"),
            "version": summary.get("version"),
            "versionUnimplemented": bool(summary.get("versionUnimplemented")),
        }
    }
    # The unimplemented-version branch reports only through gbfsResult, so
    # leaving it out would compare two empty summaries and call them equal.
    if "gbfsResult" in summary:
        out["summary"]["gbfsResult"] = norm_file(0, summary["gbfsResult"])
    if "files" in report:
        out["files"] = [norm_file(i, f) for i, f in enumerate(report["files"])]
    return out


def run_upstream(url: str, options: dict[str, Any]) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "node",
            str(ROOT / "tools/node/run_upstream.js"),
            json.dumps({"url": url, "options": options}),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 3:
        return {"critical": True, "why": proc.stderr.strip()}
    proc.check_returncode()
    try:
        return {"report": json.loads(proc.stdout)}
    except json.JSONDecodeError:
        return {"harness_error": proc.stdout[:500]}


def run_ours(url: str, options: dict[str, Any]) -> dict[str, Any]:
    try:
        report = GBFS(
            url,
            docked=bool(options.get("docked")),
            freefloating=bool(options.get("freefloating")),
            version=options.get("version"),
        ).validation()
    except Exception as exc:  # noqa: BLE001 - upstream crashes are in scope
        return {"critical": True, "why": str(exc)}
    return {"report": report}


def compare(feed_dir: pathlib.Path) -> bool:
    meta = json.loads((feed_dir / "meta.json").read_text())
    options = meta.get("options") or {}
    with serve(feed_dir) as base:
        # A feed can ask to be reached at something other than /gbfs.json, to
        # exercise the autodiscovery fallback.
        url = base + meta.get("path", "/gbfs.json")
        theirs_raw = run_upstream(url, options)
        ours_raw = run_ours(url, options)

    theirs, ours = normalize(theirs_raw), normalize(ours_raw)
    if theirs == ours:
        note = " (both crash)" if theirs.get("critical") else ""
        print(f"ok   {feed_dir.name}{note}")
        return True

    print(f"DIFF {feed_dir.name}")
    if theirs_raw.get("critical") != ours_raw.get("critical"):
        print(f"  upstream crashed: {theirs_raw.get('why', 'no')}")
        print(f"  ours crashed:     {ours_raw.get('why', 'no')}")
    print("  upstream:", json.dumps(theirs, indent=2, default=str))
    print("  ours:    ", json.dumps(ours, indent=2, default=str))
    return False


def record_expectations(feeds: list[pathlib.Path]) -> None:
    """Snapshot upstream's verdict per feed so plain CI can check it offline."""
    recorded: dict[str, Any] = {}
    for feed_dir in feeds:
        meta = json.loads((feed_dir / "meta.json").read_text())
        with serve(feed_dir) as base:
            url = base + meta.get("path", "/gbfs.json")
            recorded[feed_dir.name] = normalize(run_upstream(url, meta.get("options") or {}))
        print(f"recorded {feed_dir.name}")
    out = FEEDS / "expectations.json"
    out.write_text(json.dumps(recorded, indent=1, sort_keys=True, default=str) + "\n")
    print(f"\nwrote {out} for {len(recorded)} feeds")


def main() -> int:
    feeds = sorted(p for p in FEEDS.iterdir() if p.is_dir())
    if not feeds:
        print("no corpus feeds found", file=sys.stderr)
        return 1
    if "--write-expectations" in sys.argv:
        record_expectations(feeds)
        return 0
    failures = [feed for feed in feeds if not compare(feed)]
    print(f"\n{len(feeds) - len(failures)}/{len(feeds)} feeds at parity")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
