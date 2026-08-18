import json
import pathlib

import pytest

from gbfs_validator.constants.error_ids import AppError
from gbfs_validator.partials import get_partial_schema

GOLDENS = json.loads((pathlib.Path(__file__).parent / "fixtures/partials/goldens.json").read_text())

PARAMS = {
    "required_vehicle_type_id": {
        "vehicleTypes": [
            {
                "vehicle_type_id": "ebike1",
                "form_factor": "bicycle",
                "propulsion_type": "electric_assist",
            },
            {"vehicle_type_id": "human1", "form_factor": "bicycle", "propulsion_type": "human"},
        ]
    },
    "required_vehicle_types_available": {
        "vehicleTypes": [
            {
                "vehicle_type_id": "ebike1",
                "form_factor": "bicycle",
                "propulsion_type": "electric_assist",
            }
        ]
    },
    "required_store_uri": {"ios": True, "android": False},
    "pricing_plan_id": {"pricingPlans": [{"plan_id": "p1"}, {"plan_id": "p2"}]},
    "default_reserve_time_require": {"pricingPlansIdsWithReservationPrice": ["p1"]},
}


def test_all_19_partials_match_upstream():
    assert len(GOLDENS) == 19
    for key, expected in GOLDENS.items():
        version, name = key.split("/", 1)
        stem = name.rsplit("/", 1)[1]
        assert get_partial_schema(version, name, PARAMS[stem]) == expected, key


def test_a_plan_without_a_plan_id_is_fatal_the_way_it_is_upstream():
    # Upstream puts `undefined` in the enum and AJV then dies compiling it
    # ("Cannot read properties of undefined (reading 'replace')"), so the feed
    # gets no report on either side. An explicit null is fine there and here.
    with pytest.raises(AppError):
        get_partial_schema("2.3", "vehicle_types/pricing_plan_id", {"pricingPlans": [{}]})
    with pytest.raises(AppError):
        get_partial_schema("2.3", "vehicle_types/pricing_plan_id", {"pricingPlans": [42]})
    partial = get_partial_schema(
        "2.3", "vehicle_types/pricing_plan_id", {"pricingPlans": [{"plan_id": None}]}
    )
    assert partial is not None


def test_unregistered_partial_returns_none():
    assert get_partial_schema("1.1", "system_information/required_store_uri", {}) is None
    assert get_partial_schema("2.1", "vehicle_types/pricing_plan_id", {}) is None
