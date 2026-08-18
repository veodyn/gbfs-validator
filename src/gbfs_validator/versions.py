"""File-requirement tables ported from upstream versions/v*.js."""

DOCKED = "docked"
FREEFLOATING = "freefloating"

_V1_0 = (
    ("system_information", True),
    ("station_information", DOCKED),
    ("station_status", DOCKED),
    ("free_bike_status", FREEFLOATING),
    ("system_hours", False),
    ("system_calendar", False),
    ("system_regions", False),
    ("system_pricing_plans", False),
    ("system_alerts", False),
)

_V1_1 = (("gbfs_versions", False), *_V1_0)

_V2_1 = (
    ("gbfs_versions", False),
    ("system_information", True),
    ("vehicle_types", False),
    ("station_information", DOCKED),
    ("station_status", DOCKED),
    ("free_bike_status", FREEFLOATING),
    ("system_hours", False),
    ("system_calendar", False),
    ("system_regions", False),
    ("system_pricing_plans", False),
    ("system_alerts", False),
    ("geofencing_zones", False),
)

_V3_0 = (
    ("manifest", False),
    ("gbfs_versions", False),
    ("system_information", True),
    ("vehicle_types", False),
    ("station_information", DOCKED),
    ("station_status", DOCKED),
    ("vehicle_status", FREEFLOATING),
    ("system_regions", False),
    ("system_pricing_plans", False),
    ("system_alerts", False),
    ("geofencing_zones", False),
)

_V3_1_RC3 = (*_V3_0[:7], ("vehicle_availability", False), *_V3_0[7:])

_TABLES: dict[str, tuple[tuple[str, bool | str], ...]] = {
    "1.0": _V1_0,
    "1.1": _V1_1,
    "2.0": _V1_1,
    "2.1": _V2_1,
    "2.2": _V2_1,
    "2.3": _V2_1,
    "3.0": _V3_0,
    "3.1-RC3": _V3_1_RC3,
}

_GBFS_REQUIRED: dict[str, bool] = {
    "1.0": False,
    "1.1": False,
    "2.0": True,
    "2.1": True,
    "2.2": True,
    "2.3": True,
    "3.0": True,
    "3.1-RC3": True,
}

KNOWN_VERSIONS: tuple[str, ...] = tuple(_TABLES)


def gbfs_required(version: str) -> bool:
    """Whether gbfs.json itself is required by this version."""
    return _GBFS_REQUIRED[version]


def _resolve(flag: bool | str, docked: bool, freefloating: bool) -> bool:
    if flag == DOCKED:
        return docked
    if flag == FREEFLOATING:
        return freefloating
    return bool(flag)


def files_for(version: str, docked: bool, freefloating: bool) -> list[dict]:
    """The version's files in upstream order, with conditional flags resolved."""
    return [
        {"file": name, "required": _resolve(flag, docked, freefloating)}
        for name, flag in _TABLES[version]
    ]
