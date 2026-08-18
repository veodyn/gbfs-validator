"""The cross-file conditional rules, ported from the switch in gbfs.js:730.

Every test here is JavaScript truthiness on unvalidated feed data, so an empty
string id or a zero price triggers nothing while an empty array or object
triggers everything. That is upstream's behavior and the differential depends
on it.
"""

from __future__ import annotations

from typing import Any

from gbfs_validator.feedhelpers import (
    file_exist,
    get_pricing_plans,
    get_vehicle_types,
    had_vehicle_type_id,
    has_pricing_plan_id,
    has_rental_uris,
    prop,
)
from gbfs_validator.jstruth import truthy
from gbfs_validator.partials import get_partial_schema

Context = dict[str, Any]


def _has_length(value: Any) -> bool:
    """`value && value.length`: only arrays and strings carry a length in JS."""
    return isinstance(value, (list, str)) and len(value) > 0


def find_type(files: list[dict[str, Any]], file_type: str) -> dict[str, Any] | None:
    return next((f for f in files if f.get("type") == file_type), None)


def conditional_context(files: list[dict[str, Any]]) -> Context:
    vehicle_types_file = find_type(files, "vehicle_types")
    free_bike_status_file = find_type(files, "free_bike_status")
    station_information_file = find_type(files, "station_information")
    pricing_plans_file = find_type(files, "system_pricing_plans")

    context: Context = {
        "vehicleTypes": None,
        "pricingPlans": None,
        "freeBikeStatusHasVehicleTypeId": None,
        "hasIosRentalUris": None,
        "hasAndroidRentalUris": None,
        "hasBikesPricingPlanId": None,
    }

    if vehicle_types_file is not None and file_exist(vehicle_types_file):
        context["vehicleTypes"] = get_vehicle_types(vehicle_types_file)

    if free_bike_status_file is not None and file_exist(free_bike_status_file):
        context["freeBikeStatusHasVehicleTypeId"] = had_vehicle_type_id(free_bike_status_file)
        context["hasIosRentalUris"] = has_rental_uris(free_bike_status_file, "bikes", "ios")
        context["hasAndroidRentalUris"] = has_rental_uris(free_bike_status_file, "bikes", "android")
        context["hasBikesPricingPlanId"] = has_pricing_plan_id(free_bike_status_file)

    if station_information_file is not None and file_exist(station_information_file):
        context["hasIosRentalUris"] = context["hasIosRentalUris"] or has_rental_uris(
            station_information_file, "stations", "ios"
        )
        context["hasAndroidRentalUris"] = context["hasAndroidRentalUris"] or has_rental_uris(
            station_information_file, "stations", "android"
        )

    if pricing_plans_file is not None and file_exist(pricing_plans_file):
        context["pricingPlans"] = get_pricing_plans(pricing_plans_file)

    return context


def partials_for(
    version: str, file: dict[str, Any], context: Context
) -> tuple[list[dict[str, Any]], Any]:
    """Schema patches for one file, plus its possibly promoted `required`."""
    add_schema: list[dict[str, Any]] = []
    required = file.get("required")
    file_type = file.get("type")
    vehicle_types = context["vehicleTypes"]
    has_vehicle_types = _has_length(vehicle_types)

    if file_type == "station_status" and has_vehicle_types:
        _add(
            add_schema,
            version,
            "station_status/required_vehicle_types_available",
            {"vehicleTypes": vehicle_types},
        )
    elif file_type == "free_bike_status" and has_vehicle_types:
        _add(
            add_schema,
            version,
            "free_bike_status/required_vehicle_type_id",
            {"vehicleTypes": vehicle_types},
        )
    elif file_type == "vehicle_status" and has_vehicle_types:
        _add(
            add_schema,
            version,
            "vehicle_status/required_vehicle_type_id",
            {"vehicleTypes": vehicle_types},
        )
    elif file_type == "vehicle_types":
        required = _vehicle_types_rules(add_schema, version, context, required)
    elif file_type == "system_pricing_plans":
        if context["hasBikesPricingPlanId"]:
            required = True
    elif file_type == "system_information":
        _system_information_rules(add_schema, version, context)

    return add_schema, required


def _vehicle_types_rules(
    add_schema: list[dict[str, Any]], version: str, context: Context, required: Any
) -> Any:
    if context["freeBikeStatusHasVehicleTypeId"]:
        required = True
    plans = context["pricingPlans"]
    if not _has_length(plans):
        return required

    _add(add_schema, version, "vehicle_types/pricing_plan_id", {"pricingPlans": plans})
    # Truthiness, so a zero price does not count as a reservation price while an
    # empty object does.
    reserved = [
        prop(plan, "plan_id", "pricing plan")
        for plan in plans
        if truthy(prop(plan, "reservation_price_flat_rate", "pricing plan"))
        or truthy(prop(plan, "reservation_price_per_min", "pricing plan"))
    ]
    if reserved:
        _add(
            add_schema,
            version,
            "vehicle_types/default_reserve_time_require",
            {"pricingPlansIdsWithReservationPrice": reserved},
        )
    return required


def _system_information_rules(
    add_schema: list[dict[str, Any]], version: str, context: Context
) -> None:
    ios = context["hasIosRentalUris"]
    android = context["hasAndroidRentalUris"]
    if android or ios:
        _add(
            add_schema,
            version,
            "system_information/required_store_uri",
            {"ios": bool(ios), "android": bool(android)},
        )


def _add(add_schema: list[dict[str, Any]], version: str, name: str, params: dict[str, Any]) -> None:
    partial = get_partial_schema(version, name, params)
    if partial:
        add_schema.append(partial)
