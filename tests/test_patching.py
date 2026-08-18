import pytest

from gbfs_validator.schema.patching import apply_json_patch, apply_merge_patch
from gbfs_validator.validate import validate_file


def test_json_patch_add_into_array_index_zero():
    doc = {"required": ["a"]}
    out = apply_json_patch(doc, [{"op": "add", "path": "/required/0", "value": "z"}])
    assert out["required"] == ["z", "a"]
    assert doc["required"] == ["a"]


def test_json_patch_add_replace_remove_and_append():
    doc = {"a": {"b": [1, 2]}, "c": 1}
    assert apply_json_patch(doc, [{"op": "add", "path": "/a/b/-", "value": 3}])["a"]["b"] == [
        1,
        2,
        3,
    ]
    assert apply_json_patch(doc, [{"op": "replace", "path": "/c", "value": 9}])["c"] == 9
    assert "c" not in apply_json_patch(doc, [{"op": "remove", "path": "/c"}])


def test_json_patch_escaped_pointer_tokens():
    doc = {"a/b": {"c~d": 1}}
    out = apply_json_patch(doc, [{"op": "replace", "path": "/a~1b/c~0d", "value": 2}])
    assert out["a/b"]["c~d"] == 2


def test_json_patch_rejects_unsupported_op():
    with pytest.raises(Exception, match="copy"):
        apply_json_patch({}, [{"op": "copy", "from": "/a", "path": "/b"}])


def test_merge_patch_deep_merge_and_null_delete():
    out = apply_merge_patch({"a": {"b": 1, "c": 2}}, {"a": {"b": None, "d": 3}})
    assert out == {"a": {"c": 2, "d": 3}}


def test_merge_patch_replaces_arrays_wholesale():
    assert apply_merge_patch({"a": [1, 2, 3]}, {"a": [9]}) == {"a": [9]}


def test_merge_patch_does_not_mutate_source():
    doc = {"a": {"b": 1}}
    apply_merge_patch(doc, {"a": {"c": 2}})
    assert doc == {"a": {"b": 1}}


def test_validate_file_applies_partial_and_reports_required():
    schema = {"$id": "X", "type": "object", "properties": {"v": {"type": "string"}}}
    partial = {"$merge": {"source": {"$ref": "X"}, "with": {"required": ["v"]}}}
    result = validate_file(schema, {}, [partial])
    assert [e["keyword"] for e in result["errors"]] == ["required"]
    assert result["schema"]["required"] == ["v"]


def test_validate_file_filters_the_if_error_and_keeps_the_then_error():
    schema = {
        "$id": "X",
        "type": "object",
        "if": {"required": ["a"]},
        "then": {"required": ["b"]},
    }
    result = validate_file(schema, {"a": 1})
    assert [e["keyword"] for e in result["errors"]] == ["required"]


def test_validate_file_filters_patch_and_merge_keywords():
    # Constructed by hand: with strict off, AJV ignores $patch/$merge rather
    # than erroring on them, so upstream's filter only ever sees these if a
    # future schema makes them assert. Pin the filter itself.
    from gbfs_validator import validate as validate_module

    assert set(validate_module._FILTERED_KEYWORDS) == {"$patch", "$merge", "if"}
    errors = [
        {"keyword": "$patch", "instancePath": "", "schemaPath": "#", "params": {}, "message": ""},
        {"keyword": "$merge", "instancePath": "", "schemaPath": "#", "params": {}, "message": ""},
        {"keyword": "required", "instancePath": "", "schemaPath": "#", "params": {}, "message": ""},
    ]
    kept = [e for e in errors if e["keyword"] not in validate_module._FILTERED_KEYWORDS]
    assert [e["keyword"] for e in kept] == ["required"]


def test_validate_file_rejects_wrong_source():
    schema = {"$id": "X", "type": "object"}
    partial = {"$patch": {"source": {"$ref": "Y"}, "with": []}}
    with pytest.raises(ValueError, match="not the same as the document"):
        validate_file(schema, {}, [partial])


def test_validate_file_rejects_wrong_merge_source():
    schema = {"$id": "X", "type": "object"}
    partial = {"$merge": {"source": {"$ref": "Y"}, "with": {}}}
    with pytest.raises(ValueError, match="not the same as the document"):
        validate_file(schema, {}, [partial])


def test_validate_file_valid_returns_errors_false():
    assert validate_file({"$id": "X", "type": "object"}, {})["errors"] is False


def test_validate_file_does_not_mutate_the_input_schema():
    schema = {"$id": "X", "type": "object", "required": ["a"]}
    partial = {
        "$patch": {
            "source": {"$ref": "X"},
            "with": [{"op": "add", "path": "/required/0", "value": "z"}],
        }
    }
    validate_file(schema, {}, [partial])
    assert schema["required"] == ["a"]


def test_validate_file_applies_patch_then_merge_in_order():
    schema = {"$id": "X", "type": "object", "required": ["a"]}
    partial = {
        "$patch": {
            "source": {"$ref": "X"},
            "with": [{"op": "add", "path": "/required/0", "value": "z"}],
        },
        "$merge": {"source": {"$ref": "X"}, "with": {"properties": {"z": {"type": "string"}}}},
    }
    result = validate_file(schema, {"a": 1, "z": 2}, [partial])
    assert result["schema"]["required"] == ["z", "a"]
    assert [e["instancePath"] for e in result["errors"]] == ["/z"]
