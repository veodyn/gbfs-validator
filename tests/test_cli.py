import json
import os
import pathlib
import subprocess
import sys

import pytest

from conftest import write_feed
from gbfs_validator.cli import main


def test_prints_json_report(tmp_feed, capsys):
    assert main(["-u", tmp_feed.base]) == 0
    report = json.loads(capsys.readouterr().out)
    assert "summary" in report
    assert report["summary"]["version"] == {"detected": "2.3", "validated": "2.3"}
    assert any(f["file"] == "system_information.json" for f in report["files"])


def test_schema_and_body_stripped_by_default(tmp_feed, capsys):
    assert main(["-u", tmp_feed.base]) == 0
    out = json.loads(capsys.readouterr().out)
    for entry in out["files"]:
        assert "schema" not in entry
        assert "body" not in entry
        for lang in entry.get("languages", []):
            assert "schema" not in lang
            assert "body" not in lang


def test_include_schema_keeps_schema_but_never_body(tmp_feed, capsys):
    assert main(["-u", tmp_feed.base, "--include-schema"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert any("schema" in entry for entry in out["files"])
    languages = [lang for entry in out["files"] for lang in entry.get("languages", [])]
    assert languages
    assert all("schema" in lang for lang in languages)
    assert all("body" not in lang for lang in languages)


def test_api_report_is_not_stripped(tmp_feed):
    from gbfs_validator import validate_feed

    report = validate_feed(tmp_feed.base)
    assert any("schema" in entry for entry in report["files"])
    languages = [lang for entry in report["files"] for lang in entry.get("languages", [])]
    assert all("body" in lang for lang in languages)


def test_save_report_creates_parent_directories(tmp_feed, tmp_path, capsys):
    dest = tmp_path / "out/sub/report.json"
    assert main(["-u", tmp_feed.base, "-pr", "no", "-s", str(dest)]) == 0
    saved = json.loads(dest.read_text())
    assert "summary" in saved
    assert capsys.readouterr().out == ""


def test_neither_print_nor_save_returns_one(tmp_feed, capsys):
    assert main(["-u", tmp_feed.base, "-pr", "no"]) == 1
    assert "--save-report" in capsys.readouterr().err


def test_fail_on_error(tmp_feed_with_errors, tmp_path, capsys):
    dest = str(tmp_path / "report.json")
    assert main(["-u", tmp_feed_with_errors.base, "-pr", "no", "-s", dest]) == 0
    assert main(["-u", tmp_feed_with_errors.base, "-pr", "no", "-s", dest, "--fail-on-error"]) == 1


def test_fail_on_error_is_silent_on_a_clean_feed(tmp_feed, capsys):
    assert main(["-u", tmp_feed.base, "--fail-on-error"]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["hasErrors"] is False


def test_critical_error_returns_one(capsys):
    from fixtureserver import serve

    feed = pathlib.Path(__file__).parent / "fixtures/feeds/v2.3-malformed-vehicle-types"
    with serve(feed) as base:
        assert main(["-u", base + "/gbfs.json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Critical error while validating GBFS feed =>")


def test_unwritable_save_path_returns_one(tmp_feed, tmp_path, capsys):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    dest = blocker / "sub" / "report.json"
    assert main(["-u", tmp_feed.base, "-pr", "no", "-s", str(dest)]) == 1
    assert capsys.readouterr().err.startswith("Critical error while validating GBFS feed =>")


def test_save_path_that_is_a_directory_returns_one(tmp_feed, tmp_path, capsys):
    assert main(["-u", tmp_feed.base, "-pr", "no", "-s", str(tmp_path)]) == 1
    assert capsys.readouterr().err.startswith("Critical error while validating GBFS feed =>")


def test_broken_stdout_pipe_returns_one(tmp_path):
    write_feed(tmp_path, tmp_path.resolve().as_uri())
    # Closing the read end before spawning makes every child write fail with
    # EPIPE, with no dependency on how fast the child starts.
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    try:
        proc = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-m", "gbfs_validator.cli", "-u", str(tmp_path)],
            stdout=write_fd,
            stderr=subprocess.PIPE,
            text=True,
        )
    finally:
        os.close(write_fd)
    err = proc.communicate(timeout=120)[1]
    assert proc.returncode == 1
    assert err.startswith("Critical error while validating GBFS feed =>")


def test_local_directory_feed_validates(tmp_path, capsys):
    write_feed(tmp_path, tmp_path.resolve().as_uri())
    assert main(["-u", str(tmp_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["summary"]["version"]["detected"] == "2.3"
    entry = next(f for f in report["files"] if f["file"] == "system_information.json")
    assert entry["exists"] is True


def test_local_gbfs_json_path_validates(tmp_path, capsys):
    write_feed(tmp_path, tmp_path.resolve().as_uri())
    assert main(["-u", str(tmp_path / "gbfs.json")]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["hasErrors"] is False


def test_local_directory_without_gbfs_json(tmp_path, capsys):
    (tmp_path / "system_information.json").write_text("{}")
    assert main(["-u", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["versionUnimplemented"] is True


def test_feed_version_override(tmp_feed, capsys):
    assert main(["-u", tmp_feed.base, "--feed-version", "2.2"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["summary"]["version"] == {"detected": "2.3", "validated": "2.2"}


def test_docked_and_free_floating_change_the_file_list(tmp_feed, capsys):
    assert main(["-u", tmp_feed.base]) == 0
    plain = {f["file"] for f in json.loads(capsys.readouterr().out)["files"]}
    assert main(["-u", tmp_feed.base, "--docked"]) == 0
    docked = json.loads(capsys.readouterr().out)["files"]
    assert main(["-u", tmp_feed.base, "--free-floating"]) == 0
    freefloating = json.loads(capsys.readouterr().out)["files"]

    assert plain == {f["file"] for f in docked} == {f["file"] for f in freefloating}
    required = {f["file"] for f in docked if f["required"]}
    assert "station_information.json" in required
    assert "free_bike_status.json" in {f["file"] for f in freefloating if f["required"]}


def test_verbose_writes_to_stderr_only(tmp_feed, capsys):
    assert main(["-u", tmp_feed.base, "-vb"]) == 0
    captured = capsys.readouterr()
    json.loads(captured.out)
    assert tmp_feed.base in captured.err


def test_version_flag(capsys):
    from gbfs_validator.version import __version__

    assert main(["-v"]) == 0
    assert capsys.readouterr().out.strip().endswith(__version__)


def test_help_flag(capsys):
    assert main(["--help"]) == 0
    assert "--print-report" in capsys.readouterr().out


def test_missing_url_is_argparse_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2


def test_bad_print_report_choice_is_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        main(["-u", "http://example.invalid", "-pr", "maybe"])
    assert excinfo.value.code == 2
