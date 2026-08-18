import pytest

from gbfs_validator.versions import KNOWN_VERSIONS, files_for, gbfs_required


def test_known_versions():
    assert KNOWN_VERSIONS == ("1.0", "1.1", "2.0", "2.1", "2.2", "2.3", "3.0", "3.1-RC3")


def test_gbfs_required():
    assert gbfs_required("1.0") is False
    assert gbfs_required("1.1") is False
    assert gbfs_required("2.0") is True
    assert gbfs_required("3.1-RC3") is True


def test_gbfs_required_all_versions():
    assert [gbfs_required(v) for v in KNOWN_VERSIONS] == [
        False,
        False,
        True,
        True,
        True,
        True,
        True,
        True,
    ]


def test_gbfs_required_unknown_version_raises():
    with pytest.raises(KeyError):
        gbfs_required("4.0")


def test_v1_0_table():
    files = files_for("1.0", docked=True, freefloating=False)
    assert files[0] == {"file": "system_information", "required": True}
    assert {"file": "station_information", "required": True} in files
    assert {"file": "free_bike_status", "required": False} in files
    assert len(files) == 9


def test_v3_0_table_order_and_flags():
    files = files_for("3.0", docked=False, freefloating=True)
    assert [f["file"] for f in files] == [
        "manifest",
        "gbfs_versions",
        "system_information",
        "vehicle_types",
        "station_information",
        "station_status",
        "vehicle_status",
        "system_regions",
        "system_pricing_plans",
        "system_alerts",
        "geofencing_zones",
    ]
    assert files[6] == {"file": "vehicle_status", "required": True}


def test_v3_1_rc3_has_vehicle_availability():
    names = [f["file"] for f in files_for("3.1-RC3", docked=False, freefloating=False)]
    assert "vehicle_availability" in names and len(names) == 12


def test_unknown_version_raises():
    with pytest.raises(KeyError):
        files_for("4.0", docked=False, freefloating=False)


V1_0 = [
    ("system_information", "T"),
    ("station_information", "D"),
    ("station_status", "D"),
    ("free_bike_status", "F"),
    ("system_hours", "f"),
    ("system_calendar", "f"),
    ("system_regions", "f"),
    ("system_pricing_plans", "f"),
    ("system_alerts", "f"),
]
V1_1 = [("gbfs_versions", "f"), *V1_0]
V2_1 = [
    ("gbfs_versions", "f"),
    ("system_information", "T"),
    ("vehicle_types", "f"),
    ("station_information", "D"),
    ("station_status", "D"),
    ("free_bike_status", "F"),
    ("system_hours", "f"),
    ("system_calendar", "f"),
    ("system_regions", "f"),
    ("system_pricing_plans", "f"),
    ("system_alerts", "f"),
    ("geofencing_zones", "f"),
]
V3_0 = [
    ("manifest", "f"),
    ("gbfs_versions", "f"),
    ("system_information", "T"),
    ("vehicle_types", "f"),
    ("station_information", "D"),
    ("station_status", "D"),
    ("vehicle_status", "F"),
    ("system_regions", "f"),
    ("system_pricing_plans", "f"),
    ("system_alerts", "f"),
    ("geofencing_zones", "f"),
]
V3_1 = [*V3_0[:7], ("vehicle_availability", "f"), *V3_0[7:]]

EXPECTED = {
    "1.0": V1_0,
    "1.1": V1_1,
    "2.0": V1_1,
    "2.1": V2_1,
    "2.2": V2_1,
    "2.3": V2_1,
    "3.0": V3_0,
    "3.1-RC3": V3_1,
}


@pytest.mark.parametrize("docked", [False, True])
@pytest.mark.parametrize("freefloating", [False, True])
def test_every_table_matches_upstream(docked: bool, freefloating: bool):
    resolve = {"T": True, "f": False, "D": docked, "F": freefloating}
    for version, table in EXPECTED.items():
        assert files_for(version, docked=docked, freefloating=freefloating) == [
            {"file": name, "required": resolve[flag]} for name, flag in table
        ], version
