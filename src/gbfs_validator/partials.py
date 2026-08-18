"""Port of upstream's 19 partial schema generators.

Across versions the generators differ only in the `source.$ref` string, and
pre-3.0 in the `bikes`/`vehicles` container name, so the bodies are shared and
the refs live in a table. Each ref is copied verbatim from its upstream file:
`validate_file` matches it against the schema `$id`.
"""

from typing import Any

from gbfs_validator.constants.error_ids import AppError, ErrorIds

_MOTOR = ("electric_assist", "electric", "combustion")

_SOURCE_REFS: dict[tuple[str, str], str] = {
    (
        "2.1",
        "free_bike_status/required_vehicle_type_id",
    ): "https://github.com/MobilityData/gbfs/blob/v2.1/gbfs.md#free_bike_statusjson",
    (
        "2.1",
        "station_status/required_vehicle_types_available",
    ): "https://github.com/MobilityData/gbfs/blob/v2.1/gbfs.md#station_statusjson",
    (
        "2.1",
        "system_information/required_store_uri",
    ): "https://github.com/MobilityData/gbfs/blob/v2.1/gbfs.md#system_informationjson",
    (
        "2.2",
        "free_bike_status/required_vehicle_type_id",
    ): "https://github.com/MobilityData/gbfs/blob/v2.2/gbfs.md#free_bike_statusjson",
    (
        "2.2",
        "station_status/required_vehicle_types_available",
    ): "https://github.com/MobilityData/gbfs/blob/v2.2/gbfs.md#station_statusjson",
    (
        "2.2",
        "system_information/required_store_uri",
    ): "https://github.com/MobilityData/gbfs/blob/v2.2/gbfs.md#system_informationjson",
    (
        "2.3",
        "free_bike_status/required_vehicle_type_id",
    ): "https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#free_bike_statusjson",
    (
        "2.3",
        "station_status/required_vehicle_types_available",
    ): "https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#station_statusjson",
    (
        "2.3",
        "system_information/required_store_uri",
    ): "https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#system_informationjson",
    (
        "2.3",
        "vehicle_types/pricing_plan_id",
    ): "https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#vehicle_typesjson",
    (
        "3.0",
        "station_status/required_vehicle_types_available",
    ): "https://github.com/MobilityData/gbfs/blob/v3.0/gbfs.md#station_statusjson",
    (
        "3.0",
        "system_information/required_store_uri",
    ): "https://github.com/MobilityData/gbfs/blob/v3.0/gbfs.md#system_informationjson",
    (
        "3.0",
        "vehicle_status/required_vehicle_type_id",
    ): "https://github.com/MobilityData/gbfs/blob/v3.0/gbfs.md#vehicle_statusjson",
    (
        "3.0",
        "vehicle_types/pricing_plan_id",
    ): "https://github.com/MobilityData/gbfs/blob/v3.0/gbfs.md#vehicle_typesjson",
    (
        "3.1-RC3",
        "station_status/required_vehicle_types_available",
    ): "https://github.com/MobilityData/gbfs-json-schema/blob/master/v3.1-RC3/station_status.json",
    (
        "3.1-RC3",
        "system_information/required_store_uri",
    ): "https://github.com/MobilityData/gbfs-json-schema/blob/master/v3.1-RC3/system_information.json",
    (
        "3.1-RC3",
        "vehicle_status/required_vehicle_type_id",
    ): "https://github.com/MobilityData/gbfs-json-schema/blob/master/v3.1-RC3/vehicle_status.json",
    (
        "3.1-RC3",
        "vehicle_types/default_reserve_time_require",
    ): "https://github.com/MobilityData/gbfs-json-schema/blob/master/v3.1-RC3/vehicle_types.json",
    (
        "3.1-RC3",
        "vehicle_types/pricing_plan_id",
    ): "https://github.com/MobilityData/gbfs-json-schema/blob/master/v3.1-RC3/vehicle_types.json",
}

_CONTAINERS = {"free_bike_status": "bikes", "vehicle_status": "vehicles"}


def _required_vehicle_type_id(source_ref: str, container: str, params: dict) -> dict:
    partial: dict[str, Any] = {"$id": "required_vehicle_type_id.json#"}
    motor = [vt for vt in params["vehicleTypes"] if vt.get("propulsion_type") in _MOTOR]
    if motor:
        partial["$merge"] = {
            "source": {"$ref": source_ref},
            "with": {
                "properties": {
                    "data": {
                        "properties": {
                            container: {
                                "items": {
                                    "errorMessage": {
                                        "required": {
                                            "vehicle_type_id": "'vehicle_type_id' is required for this vehicle type"
                                        }
                                    },
                                    "if": {
                                        "properties": {
                                            "vehicle_type_id": {
                                                "enum": [vt["vehicle_type_id"] for vt in motor]
                                            }
                                        },
                                        "required": ["vehicle_type_id"],
                                    },
                                    "then": {"required": ["current_range_meters"]},
                                }
                            }
                        }
                    }
                }
            },
        }
    partial["$patch"] = {
        "source": {"$ref": source_ref},
        "with": [
            {
                "op": "add",
                "path": f"/properties/data/properties/{container}/items/required/0",
                "value": "vehicle_type_id",
            }
        ],
    }
    return partial


def _required_vehicle_types_available(source_ref: str, params: dict) -> dict:
    ids = [vt["vehicle_type_id"] for vt in params["vehicleTypes"]]
    return {
        "$id": "required_vehicle_types_available.json#",
        "$merge": {
            "source": {"$ref": source_ref},
            "with": {
                "properties": {
                    "data": {
                        "properties": {
                            "stations": {
                                "items": {
                                    "properties": {
                                        "vehicle_types_available": {
                                            "items": {
                                                "properties": {"vehicle_type_id": {"enum": ids}}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
        },
        "$patch": {
            "source": {"$ref": source_ref},
            "with": [
                {
                    "op": "add",
                    "path": "/properties/data/properties/stations/items/required/0",
                    "value": "vehicle_types_available",
                }
            ],
        },
    }


def _required_store_uri(source_ref: str, params: dict) -> dict:
    rental_apps: dict[str, Any] = {
        "required": [],
        "properties": {"ios": {"required": []}, "android": {"required": []}},
    }
    partial = {
        "$id": "required_ios_store_uri.json#",
        "$patch": {
            "source": {"$ref": source_ref},
            "with": [{"op": "add", "path": "/properties/data/required/0", "value": "rental_apps"}],
        },
        "$merge": {
            "source": {"$ref": source_ref},
            "with": {"properties": {"data": {"properties": {"rental_apps": rental_apps}}}},
        },
    }
    if params.get("ios", False):
        rental_apps["required"].append("ios")
        rental_apps["properties"]["ios"]["required"].append("store_uri")
    if params.get("android", False):
        rental_apps["required"].append("android")
        rental_apps["properties"]["android"]["required"].append("store_uri")
    return partial


def _plan_id(plan: Any) -> Any:
    """`p.plan_id`, where JS's `undefined` is fatal a few steps later.

    Upstream builds the enum with the undefined in it and AJV dies compiling
    it ("Cannot read properties of undefined (reading 'replace')"), so the feed
    gets no report on either side. An explicit null compiles and is kept.
    """
    if isinstance(plan, dict) and "plan_id" in plan:
        return plan["plan_id"]
    raise AppError(
        ErrorIds.FEED_MALFORMED_CONTAINER,
        "pricing plan has no plan_id",
        {"got": type(plan).__name__},
    )


def _pricing_plan_id(source_ref: str, params: dict) -> dict:
    ids = [_plan_id(p) for p in params["pricingPlans"]]
    return {
        "$id": "pricing_plan_id.json#",
        "$merge": {
            "source": {"$ref": source_ref},
            "with": {
                "properties": {
                    "data": {
                        "properties": {
                            "vehicle_types": {
                                "items": {"properties": {"default_pricing_plan_id": {"enum": ids}}}
                            }
                        }
                    }
                }
            },
        },
    }


def _default_reserve_time_require(source_ref: str, params: dict) -> dict:
    ids = params["pricingPlansIdsWithReservationPrice"]
    # allOf avoids overwriting the existing if statement about max_range
    condition = {
        "if": {
            "anyOf": [
                {"properties": {"default_pricing_plan_id": {"enum": ids}}},
                {"properties": {"pricing_plan_ids": {"contains": {"enum": ids}}}},
            ]
        },
        "then": {"required": ["default_reserve_time"]},
    }
    return {
        "$id": "pricing_plan_id.json#",
        "$merge": {
            "source": {"$ref": source_ref},
            "with": {
                "properties": {
                    "data": {
                        "properties": {
                            "vehicle_types": {"items": {"allOf": [condition]}},
                        }
                    }
                }
            },
        },
    }


def get_partial_schema(version: str, name: str, params: dict) -> dict | None:
    """Build one partial schema, or None when (version, name) is not registered."""
    source_ref = _SOURCE_REFS.get((version, name))
    if source_ref is None:
        return None
    directory, stem = name.split("/", 1)
    if stem == "required_vehicle_type_id":
        return _required_vehicle_type_id(source_ref, _CONTAINERS[directory], params)
    if stem == "required_vehicle_types_available":
        return _required_vehicle_types_available(source_ref, params)
    if stem == "required_store_uri":
        return _required_store_uri(source_ref, params)
    if stem == "pricing_plan_id":
        return _pricing_plan_id(source_ref, params)
    return _default_reserve_time_require(source_ref, params)
