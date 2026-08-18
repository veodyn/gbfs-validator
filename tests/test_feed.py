import json
import pathlib

import pytest

from fixtureserver import serve
from gbfs_validator.feed import GBFS

V23 = {"last_updated": 1566224400, "ttl": 0, "version": "2.3"}


def write(tmp_path: pathlib.Path, files: dict[str, dict]) -> pathlib.Path:
    for name, body in files.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(body))
    return tmp_path


def system_information_23() -> dict:
    return {
        **V23,
        "data": {
            "system_id": "s",
            "language": "en",
            "name": "S",
            "timezone": "Etc/UTC",
        },
    }


def discovery_23(feeds: list[str], lang: str = "en") -> dict:
    return {
        **V23,
        "data": {lang: {"feeds": [{"name": n, "url": "{BASE}/" + f"{n}.json"} for n in feeds]}},
    }


def by_file(report: dict, name: str) -> dict:
    return next(f for f in report["files"] if f["file"] == name)


def test_missing_url_raises():
    with pytest.raises(ValueError, match="Missing URL"):
        GBFS("")


def test_autodiscovery_v2_multilang(tmp_path):
    write(
        tmp_path,
        {
            "gbfs": discovery_23(["system_information"]),
            "system_information": system_information_23(),
        },
    )
    with serve(tmp_path) as base:
        report = GBFS(base + "/gbfs.json").validation()

    assert report["summary"]["version"] == {"detected": "2.3", "validated": "2.3"}
    entry = by_file(report, "system_information.json")
    assert [lang["lang"] for lang in entry["languages"]] == ["en"]
    assert entry["exists"] is True


def test_autodiscovery_fallback_appends_gbfs_json(tmp_path):
    write(
        tmp_path,
        {
            "gbfs": discovery_23(["system_information"]),
            "system_information": system_information_23(),
        },
    )
    with serve(tmp_path) as base:
        report = GBFS(base).validation()

    assert by_file(report, "gbfs.json")["exists"] is True


def test_no_autodiscovery_version_unimplemented(tmp_path):
    with serve(tmp_path) as base:
        report = GBFS(base + "/gbfs.json").validation()

    assert report["summary"]["versionUnimplemented"] is True
    assert "files" not in report
    # Upstream leaves gbfsVersion undefined here, so the key is absent.
    assert "gbfsVersion" not in report["summary"]


def test_v3_feed_single_language(tmp_path):
    write(
        tmp_path,
        {
            "gbfs": {
                "last_updated": "2019-08-19T10:20:00-04:00",
                "ttl": 0,
                "version": "3.0",
                "data": {
                    "feeds": [
                        {"name": "system_information", "url": "{BASE}/system_information.json"}
                    ]
                },
            },
            "system_information": {
                "last_updated": "2019-08-19T10:20:00-04:00",
                "ttl": 0,
                "version": "3.0",
                "data": {
                    "system_id": "s",
                    "languages": ["en"],
                    "name": [{"text": "S", "language": "en"}],
                    "opening_hours": "Mo-Su 00:00-23:59",
                    "timezone": "Etc/UTC",
                    "feed_contact_email": "a@b.co",
                },
            },
        },
    )
    with serve(tmp_path) as base:
        report = GBFS(base + "/gbfs.json").validation()

    entry = by_file(report, "system_information.json")
    assert entry["exists"] is True
    # v3 discovery has no per-language keys, so the entry carries no lang.
    assert "lang" not in entry["languages"][0]


def test_vehicle_types_partial_fires(tmp_path):
    write(
        tmp_path,
        {
            "gbfs": discovery_23(["system_information", "vehicle_types", "free_bike_status"]),
            "system_information": system_information_23(),
            "vehicle_types": {
                **V23,
                "data": {
                    "vehicle_types": [
                        {
                            "vehicle_type_id": "ebike1",
                            "form_factor": "bicycle",
                            "propulsion_type": "electric_assist",
                            "max_range_meters": 40000,
                        }
                    ]
                },
            },
            "free_bike_status": {
                **V23,
                "data": {
                    "bikes": [
                        {
                            "bike_id": "b1",
                            "vehicle_type_id": "ebike1",
                            "is_reserved": False,
                            "is_disabled": False,
                            "lat": 37.7,
                            "lon": -122.4,
                        }
                    ]
                },
            },
        },
    )
    with serve(tmp_path) as base:
        report = GBFS(base + "/gbfs.json", freefloating=True).validation()

    bikes = by_file(report, "free_bike_status.json")
    messages = [e["message"] for lang in bikes["languages"] for e in (lang["errors"] or [])]
    assert any("current_range_meters" in m or "vehicle_type_id" in m for m in messages)
    # A bike carrying a vehicle_type_id forces vehicle_types.json to be required.
    assert by_file(report, "vehicle_types.json")["required"] is True


def test_missing_required_file_counted(tmp_path):
    write(
        tmp_path,
        {
            "gbfs": discovery_23(["system_information", "station_information", "station_status"]),
            "system_information": system_information_23(),
            "station_information": {
                **V23,
                "data": {"stations": [{"station_id": "s1", "name": "S1", "lat": 1.0, "lon": 2.0}]},
            },
        },
    )
    with serve(tmp_path) as base:
        report = GBFS(base + "/gbfs.json", docked=True).validation()

    status = by_file(report, "station_status.json")
    assert status["exists"] is False
    assert status["required"] is True
    assert report["summary"]["hasErrors"] is True
    assert report["summary"]["errorsCount"] >= 1


def test_version_override(tmp_path):
    write(
        tmp_path,
        {
            "gbfs": {**V23, "version": "2.2", "data": {"en": {"feeds": []}}},
        },
    )
    with serve(tmp_path) as base:
        report = GBFS(base + "/gbfs.json", version="2.3").validation()

    assert report["summary"]["version"] == {"detected": "2.2", "validated": "2.3"}


def test_manifest_url_is_chased(tmp_path):
    v3 = {"last_updated": "2019-08-19T10:20:00-04:00", "ttl": 0, "version": "3.0"}
    write(
        tmp_path,
        {
            "gbfs": {
                **v3,
                "data": {
                    "feeds": [
                        {"name": "system_information", "url": "{BASE}/system_information.json"}
                    ]
                },
            },
            "system_information": {
                **v3,
                "data": {
                    "system_id": "s",
                    "languages": ["en"],
                    "name": [{"text": "S", "language": "en"}],
                    "opening_hours": "Mo-Su 00:00-23:59",
                    "timezone": "Etc/UTC",
                    "feed_contact_email": "a@b.co",
                    "manifest_url": "{BASE}/manifest.json",
                },
            },
            "manifest": {**v3, "data": {"datasets": []}},
        },
    )
    with serve(tmp_path) as base:
        report = GBFS(base + "/gbfs.json").validation()

    manifests = [f for f in report["files"] if f["file"] == "manifest.json"]
    # One from the v3 file table, one from the manifest_url chase.
    assert len(manifests) == 2


def test_manifest_url_on_a_pre_v3_feed_crashes_like_upstream(tmp_path):
    # There is no v2.3 manifest schema, so upstream's require throws
    # MODULE_NOT_FOUND and it reports "can not require". Verified against
    # upstream/gbfs-validator/versions/gbfs-json-schema/v2.3/.
    write(
        tmp_path,
        {
            "gbfs": discovery_23(["system_information"]),
            "system_information": {
                **V23,
                "data": {
                    "system_id": "s",
                    "language": "en",
                    "name": "S",
                    "timezone": "Etc/UTC",
                    "manifest_url": "{BASE}/manifest.json",
                },
            },
            "manifest": {**V23, "data": {"datasets": []}},
        },
    )
    with serve(tmp_path) as base, pytest.raises(Exception, match="can not require"):
        GBFS(base + "/gbfs.json").validation()


def test_malformed_container_crashes_like_upstream(tmp_path):
    write(
        tmp_path,
        {
            "gbfs": discovery_23(["system_information", "vehicle_types"]),
            "system_information": system_information_23(),
            "vehicle_types": {**V23, "data": {"vehicle_types": {"not": "a list"}}},
        },
    )
    with serve(tmp_path) as base, pytest.raises(Exception, match="not an array"):
        GBFS(base + "/gbfs.json").validation()


def test_every_file_entry_carries_an_errors_count(tmp_path):
    write(
        tmp_path,
        {
            "gbfs": discovery_23(["system_information"]),
            "system_information": system_information_23(),
        },
    )
    with serve(tmp_path) as base:
        report = GBFS(base + "/gbfs.json").validation()

    assert all("errorsCount" in f for f in report["files"])
    assert report["summary"]["validatorVersion"]
