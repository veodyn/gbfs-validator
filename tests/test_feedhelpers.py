"""The feed readers run on unvalidated bodies, so JS semantics decide.

Member access on a boxed primitive is `undefined` in JS, not a throw, and `[]`
and `{}` are truthy. Every expectation below was measured against the pinned
upstream validator with tools/differential.py before being written down.
"""

from __future__ import annotations

from typing import Any

import pytest

from gbfs_validator import feedhelpers as fh
from gbfs_validator.constants.error_ids import AppError


def entry(body: Any, lang: str = "en") -> dict[str, Any]:
    return {"body": body, "exists": True, "lang": lang, "url": "http://x/f.json"}


def one_language(body: Any) -> dict[str, Any]:
    return {"body": [entry(body)]}


def bikes(*items: Any) -> dict[str, Any]:
    return one_language({"data": {"bikes": list(items)}})


def test_vehicle_type_that_is_not_an_object_reads_as_three_undefined_fields() -> None:
    file = one_language({"data": {"vehicle_types": [42]}})
    assert fh.get_vehicle_types(file) == [
        {"vehicle_type_id": None, "form_factor": None, "propulsion_type": None}
    ]


def test_two_primitive_vehicle_types_collapse_because_both_ids_are_undefined() -> None:
    file = {
        "body": [
            entry({"data": {"vehicle_types": [42]}}),
            entry({"data": {"vehicle_types": ["x"]}}, "fr"),
        ]
    }
    assert len(fh.get_vehicle_types(file)) == 1


def test_missing_vehicle_types_container_still_throws() -> None:
    with pytest.raises(AppError):
        fh.get_vehicle_types(one_language({"data": {}}))


def test_pricing_plans_dedup_tolerates_items_that_are_not_objects() -> None:
    file = {"body": [entry({"data": {"plans": [42]}}), entry({"data": {"plans": ["x"]}}, "fr")]}
    assert fh.get_pricing_plans(file) == [42]


def test_empty_array_vehicle_type_id_counts_because_it_is_truthy_in_js() -> None:
    assert fh.had_vehicle_type_id(bikes({"vehicle_type_id": []})) is True


def test_empty_string_vehicle_type_id_does_not_count() -> None:
    assert fh.had_vehicle_type_id(bikes({"vehicle_type_id": ""})) is False


def test_a_bike_that_is_not_an_object_has_no_vehicle_type_id() -> None:
    assert fh.had_vehicle_type_id(bikes(42)) is False


def test_a_null_bike_throws_the_way_javascript_does() -> None:
    with pytest.raises(AppError):
        fh.had_vehicle_type_id(bikes(None))


def test_empty_object_pricing_plan_id_counts_because_it_is_truthy_in_js() -> None:
    assert fh.has_pricing_plan_id(bikes({"pricing_plan_id": {}})) is True


def test_a_bike_that_is_not_an_object_has_no_pricing_plan_id() -> None:
    assert fh.has_pricing_plan_id(bikes(42)) is False


def test_empty_object_store_uri_counts_because_it_is_truthy_in_js() -> None:
    assert fh.has_rental_uris(bikes({"rental_uris": {"ios": {}}}), "bikes", "ios") is True


def test_empty_string_store_uri_does_not_count() -> None:
    assert fh.has_rental_uris(bikes({"rental_uris": {"ios": ""}}), "bikes", "ios") is False


def test_rental_uris_on_a_bike_that_is_not_an_object() -> None:
    assert fh.has_rental_uris(bikes(42), "bikes", "ios") is False


def test_a_language_entry_without_feeds_throws() -> None:
    with pytest.raises(AppError):
        fh.find_feed({}, "system_information")


def test_a_feed_entry_that_is_not_an_object_is_skipped() -> None:
    feeds = [42, {"name": "system_information", "url": "http://x/si.json"}]
    assert fh.find_feed({"feeds": feeds}, "system_information") == feeds[1]
    assert fh.find_feed({"feeds": [42]}, "system_information") is None
