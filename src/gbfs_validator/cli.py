"""Command line entry point: validate a feed, print and/or save the JSON report."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from typing import Any

from gbfs_validator.constants.error_ids import ErrorIds
from gbfs_validator.feed import GBFS
from gbfs_validator.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gbfs-validator",
        usage="%(prog)s [OPTIONS]...",
        description="Validate a GBFS feed and report on every file it declares.",
    )
    parser.add_argument("-v", "--version", action="version", version=__version__)
    parser.add_argument(
        "-u",
        "--url",
        metavar="FEED_URL",
        required=True,
        help="URL of the GBFS feed, or a local path to a directory or a gbfs.json file",
    )
    parser.add_argument(
        "-vb", "--verbose", action="store_true", help="print progress logs to stderr"
    )
    parser.add_argument(
        "-s", "--save-report", metavar="REPORT_PATH", help="local path to write the report to"
    )
    parser.add_argument(
        "-pr",
        "--print-report",
        choices=["yes", "no"],
        default="yes",
        help="print the report as JSON to standard output (default: yes)",
    )
    parser.add_argument("--docked", action="store_true", help="feed serves a docked system")
    parser.add_argument(
        "--free-floating", action="store_true", help="feed serves a free floating system"
    )
    parser.add_argument(
        "--feed-version",
        metavar="VERSION",
        help="validate against this GBFS version instead of the detected one",
    )
    parser.add_argument(
        "--include-schema", action="store_true", help="keep the compiled schema in the report"
    )
    parser.add_argument(
        "--fail-on-error", action="store_true", help="exit 1 when the feed has validation errors"
    )
    return parser


def resolve_url(url: str) -> str:
    """An existing local path becomes a file:// URL; a directory keeps a trailing slash."""
    path = pathlib.Path(url)
    if not path.exists():
        return url
    resolved = path.resolve()
    # Without the trailing slash, urljoin drops the directory when it appends
    # gbfs.json (feed.py:69).
    return f"{resolved.as_uri()}/" if resolved.is_dir() else resolved.as_uri()


def strip_report(report: dict[str, Any], include_schema: bool) -> dict[str, Any]:
    """The CLI never echoes fetched bodies, and drops schemas unless asked for them."""
    if "files" not in report:
        return report
    drop = {"body"} if include_schema else {"body", "schema"}
    return {**report, "files": [_strip_entry(entry, drop) for entry in report["files"]]}


def _strip_entry(entry: dict[str, Any], drop: set[str]) -> dict[str, Any]:
    out = {key: value for key, value in entry.items() if key not in drop}
    languages = out.get("languages")
    if isinstance(languages, list):
        out["languages"] = [
            {key: value for key, value in lang.items() if key not in drop} for lang in languages
        ]
    return out


def _save(report_json: str, destination: str) -> None:
    path = pathlib.Path(destination)
    if path.parent != path:
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_json)


def _discard_stdout() -> None:
    """Point fd 1 at /dev/null so the interpreter's shutdown flush cannot fail too."""
    try:
        fd = sys.stdout.fileno()
    except (AttributeError, ValueError, OSError):
        return
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, fd)
    finally:
        os.close(devnull)


def _critical(err: Exception) -> int:
    """Upstream's catch-all critical path (cli.js:93)."""
    if isinstance(err, BrokenPipeError):
        _discard_stdout()
    print(f"Critical error while validating GBFS feed => {err}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_request:
        if exit_request.code:
            raise
        return 0

    if not args.save_report and args.print_report == "no":
        print(
            f"[{ErrorIds.CLI_NO_OUTPUT_REQUESTED}] Please set at least one of the following "
            f"options: --save-report or --print-report",
            file=sys.stderr,
        )
        parser.print_help(sys.stderr)
        return 1

    url = resolve_url(args.url)
    if args.verbose:
        print(f"Started GBFS validation of {url} with options: {vars(args)}", file=sys.stderr)

    # Printing and saving stay inside the catch, as upstream does (cli.js:85).
    try:
        report = GBFS(
            url,
            docked=args.docked,
            freefloating=args.free_floating,
            version=args.feed_version,
        ).validation()
        report_json = json.dumps(strip_report(report, args.include_schema))
        if args.print_report == "yes":
            print(report_json)
            # Without this, a closed stdout only fails at shutdown, past the catch.
            sys.stdout.flush()
        if args.save_report:
            _save(report_json, args.save_report)
    except Exception as err:  # noqa: BLE001 - upstream's catch-all critical path (cli.js:93)
        return _critical(err)

    if args.verbose:
        print("Validation completed", file=sys.stderr)

    if args.fail_on_error and report["summary"].get("hasErrors"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
