"""Discovery-document shapes where JavaScript semantics decide the outcome.

Every case here is pinned against the upstream validator through
`tools/differential.py`; where upstream throws, so must we.
"""

import json
import pathlib

import pytest

from fixtureserver import serve
from gbfs_validator.feed import GBFS

V23 = {"last_updated": 1566224400, "ttl": 0, "version": "2.3"}
V30 = {"last_updated": "2019-08-19T10:20:00-04:00", "ttl": 0, "version": "3.0"}


def write(tmp_path: pathlib.Path, files: dict[str, object]) -> pathlib.Path:
    for name, body in files.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(body))
    return tmp_path


def by_file(report: dict, name: str) -> dict:
    return next(f for f in report["files"] if f["file"] == name)


def test_discovery_data_array_reports_instead_of_crashing(tmp_path):
    # Object.entries([]) is [], so upstream walks zero languages and still
    # reports the schema error on /data (gbfs.js:479).
    write(tmp_path, {"gbfs": {**V23, "data": []}})
    with serve(tmp_path) as base:
        report = GBFS(base + "/gbfs.json").validation()

    assert by_file(report, "system_information.json")["languages"] == []
    assert [e["instancePath"] for e in by_file(report, "gbfs.json")["errors"]] == ["/data"]


def test_language_entry_without_feeds_crashes_like_upstream(tmp_path):
    # `data.en.feeds.find(...)` on a language entry with no feeds is
    # `undefined.find(...)`, which throws before any report exists.
    write(tmp_path, {"gbfs": {**V23, "data": {"en": {}}}})
    with serve(tmp_path) as base, pytest.raises(Exception, match="not a function"):
        GBFS(base + "/gbfs.json").validation()


def test_v3_discovery_data_null_crashes_like_upstream(tmp_path):
    # `this.autoDiscovery.data.feeds` is unguarded; only `.feeds?.` is optional.
    write(tmp_path, {"gbfs": {**V30, "data": None}})
    with serve(tmp_path) as base, pytest.raises(Exception, match="null"):
        GBFS(base + "/gbfs.json").validation()


def test_v3_feeds_entry_that_is_not_an_object_is_filtered_out(tmp_path):
    # `(42).name` is undefined rather than a throw, so the entry never matches
    # and the feed is reported as missing.
    write(tmp_path, {"gbfs": {**V30, "data": {"feeds": [42]}}})
    with serve(tmp_path) as base:
        report = GBFS(base + "/gbfs.json").validation()

    assert by_file(report, "system_information.json")["languages"] == []
    assert by_file(report, "gbfs.json")["errors"][0]["instancePath"] == "/data/feeds/0"


def test_numeric_version_is_interpolated_like_a_template_literal(tmp_path):
    # `v${2.3}` is "v2.3", so upstream loads the schema and then reports that
    # version is not a string. The report keeps the raw number.
    write(
        tmp_path,
        {
            "gbfs": {
                **V23,
                "version": 2.3,
                "data": {
                    "en": {
                        "feeds": [
                            {"name": "system_information", "url": "{BASE}/system_information.json"}
                        ]
                    }
                },
            },
            "system_information": {
                **V23,
                "data": {"system_id": "s", "language": "en", "name": "S", "timezone": "Etc/UTC"},
            },
        },
    )
    with serve(tmp_path) as base:
        report = GBFS(base + "/gbfs.json").validation()

    assert report["summary"]["version"] == {"detected": 2.3, "validated": 2.3}
    assert sorted(e["keyword"] for e in by_file(report, "gbfs.json")["errors"]) == ["const", "type"]


def test_integral_numeric_version_drops_its_decimal(tmp_path):
    # `v${3.0}` is "v3", which no schema directory matches. The throw happens
    # inside checkAutodiscovery's promise chain, so its catch turns it into a
    # missing gbfs.json and the run ends as versionUnimplemented.
    write(tmp_path, {"gbfs": {**V30, "version": 3.0, "data": {"feeds": []}}})
    with serve(tmp_path) as base:
        report = GBFS(base + "/gbfs.json").validation()

    assert report["summary"]["versionUnimplemented"] is True
    assert report["summary"]["gbfsResult"]["exists"] is False


def test_manifest_lookup_optional_chains_through_a_null_data(tmp_path):
    # gbfs.js:660 chains with `?.` the whole way, so a system_information whose
    # data is null just has no manifest_url and the file is reported on.
    write(
        tmp_path,
        {
            "gbfs": {
                **V30,
                "data": {
                    "feeds": [
                        {"name": "system_information", "url": "{BASE}/system_information.json"}
                    ]
                },
            },
            "system_information": {**V30, "data": None},
        },
    )
    with serve(tmp_path) as base:
        report = GBFS(base + "/gbfs.json").validation()

    assert [f["file"] for f in report["files"]].count("manifest.json") == 1
    assert by_file(report, "system_information.json")["hasErrors"] is True


def test_unescaped_dot_in_the_autodiscovery_regex_matches_any_character(tmp_path):
    # Upstream tests /gbfs.json$/ against the URL, where the dot is unescaped,
    # so /gbfs_json counts as an autodiscovery URL and never falls back.
    write(
        tmp_path,
        {
            "gbfs": {
                **V23,
                "data": {
                    "en": {
                        "feeds": [
                            {"name": "system_information", "url": "{BASE}/system_information.json"}
                        ]
                    }
                },
            },
        },
    )
    with serve(tmp_path) as base:
        report = GBFS(base + "/gbfs_json").validation()

    assert report["summary"]["versionUnimplemented"] is True


def test_null_body_on_the_fallback_path_reports_a_missing_gbfs(tmp_path):
    # `body.version` throws on a null body, and alternativeAutoDiscovery's
    # catch turns that into exists: false rather than validating null.
    (tmp_path / "gbfs.json").write_text("null")
    with serve(tmp_path) as base:
        report = GBFS(base).validation()

    result = report["summary"]["gbfsResult"]
    assert result["exists"] is False
    assert result["errors"] is False
