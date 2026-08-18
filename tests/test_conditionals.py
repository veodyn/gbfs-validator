"""The cross-file conditional layer, pinned to upstream's measured behavior.

Upstream guards its pricing-plan work with `pricingPlans && pricingPlans.length`
and reads plan fields with JS truthiness, so a plans container that is not an
array is skipped and an empty-object price counts.
"""

from __future__ import annotations

from typing import Any

import pytest

from gbfs_validator.conditionals import conditional_context, partials_for
from gbfs_validator.constants.error_ids import AppError


def language_file(file_type: str, data: Any) -> dict[str, Any]:
    body = {"last_updated": 0, "ttl": 0, "version": "2.3", "data": data}
    return {
        "file": f"{file_type}.json",
        "type": file_type,
        "required": False,
        "body": [{"body": body, "exists": True, "lang": "en", "url": "http://x/f.json"}],
    }


VEHICLE_TYPES = language_file(
    "vehicle_types",
    {
        "vehicle_types": [
            {"vehicle_type_id": "v1", "form_factor": "bicycle", "propulsion_type": "human"}
        ]
    },
)


def plans_context(plans: Any) -> dict[str, Any]:
    return conditional_context(
        [VEHICLE_TYPES, language_file("system_pricing_plans", {"plans": plans})]
    )


def test_a_plans_container_that_is_not_an_array_adds_no_partial() -> None:
    # A single-body feed hands `data.plans` through unread, and upstream's
    # guard is `pricingPlans && pricingPlans.length`, which a number fails.
    flat = {
        "file": "system_pricing_plans.json",
        "type": "system_pricing_plans",
        "required": False,
        "exists": True,
        "body": {"data": {"plans": 42}},
    }
    context = conditional_context([VEHICLE_TYPES, flat])
    assert context["pricingPlans"] == 42
    assert partials_for("2.3", VEHICLE_TYPES, context) == ([], False)


def test_a_plans_container_that_is_not_an_array_still_throws_per_language() -> None:
    # The per-language reducer calls `.map` on it, which throws in both.
    with pytest.raises(AppError):
        plans_context(42)


def test_an_empty_plans_array_adds_no_partial() -> None:
    add_schema, _ = partials_for("2.3", VEHICLE_TYPES, plans_context([]))
    assert add_schema == []


def test_an_empty_object_reservation_price_requires_a_reserve_time() -> None:
    context = plans_context([{"plan_id": "p1", "reservation_price_per_min": {}}])
    add_schema, _ = partials_for("3.1-RC3", VEHICLE_TYPES, context)
    assert [p["$id"] for p in add_schema] == ["pricing_plan_id.json#", "pricing_plan_id.json#"]
    reserve = add_schema[1]["$merge"]["with"]["properties"]["data"]["properties"]
    condition = reserve["vehicle_types"]["items"]["allOf"][0]
    assert condition["if"]["anyOf"][0]["properties"]["default_pricing_plan_id"]["enum"] == ["p1"]


def test_a_zero_reservation_price_does_not() -> None:
    context = plans_context([{"plan_id": "p1", "reservation_price_per_min": 0}])
    add_schema, _ = partials_for("3.1-RC3", VEHICLE_TYPES, context)
    assert len(add_schema) == 1


def test_a_plan_without_a_plan_id_is_undefined_where_no_partial_consumes_it() -> None:
    # 2.2 registers neither pricing-plan partial, so upstream reaches the end
    # of the branch with an `undefined` id and reports normally.
    context = plans_context([{"reservation_price_per_min": 1}])
    assert partials_for("2.2", VEHICLE_TYPES, context) == ([], False)
