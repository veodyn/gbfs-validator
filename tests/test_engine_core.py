from gbfs_validator.schema.engine import validate_schema


def keys(errs):
    return sorted((e["instancePath"], e["keyword"]) for e in errs)


def test_valid_object_no_errors():
    schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "string"}}}
    assert validate_schema(schema, {"a": "x"}) == []


def test_type_error_shape():
    errs = validate_schema({"type": "object", "properties": {"a": {"type": "string"}}}, {"a": 1})
    assert errs == [
        {
            "instancePath": "/a",
            "schemaPath": "#/properties/a/type",
            "keyword": "type",
            "params": {"type": "string"},
            "message": "must be string",
        }
    ]


def test_required_reports_each_missing_property():
    errs = validate_schema({"type": "object", "required": ["a", "b"]}, {})
    assert keys(errs) == [("", "required"), ("", "required")]
    assert sorted(e["params"]["missingProperty"] for e in errs) == ["a", "b"]
    assert errs[0]["message"] == "must have required property 'a'"


def test_integer_accepts_float_with_zero_fraction_and_rejects_bool():
    assert validate_schema({"type": "integer"}, 1.0) == []
    assert keys(validate_schema({"type": "integer"}, True)) == [("", "type")]
    assert keys(validate_schema({"type": "number"}, False)) == [("", "type")]


def test_enum_const_limits_pattern_format():
    assert keys(validate_schema({"enum": ["a", "b"]}, "c")) == [("", "enum")]
    assert keys(validate_schema({"const": 5}, 4)) == [("", "const")]
    assert keys(validate_schema({"type": "number", "minimum": 0}, -1)) == [("", "minimum")]
    assert keys(validate_schema({"type": "number", "maximum": 90}, 91)) == [("", "maximum")]
    assert keys(validate_schema({"type": "string", "minLength": 2}, "x")) == [("", "minLength")]
    assert keys(validate_schema({"type": "string", "maxLength": 1}, "xy")) == [("", "maxLength")]
    assert keys(validate_schema({"type": "string", "pattern": "^[a-z]{2}$"}, "ABC")) == [
        ("", "pattern")
    ]
    assert keys(validate_schema({"type": "string", "format": "email"}, "nope")) == [("", "format")]
    assert validate_schema({"type": "string", "format": "unknown-format"}, "x") == []


def test_arrays_and_items():
    schema = {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 3}
    assert keys(validate_schema(schema, ["a", 1])) == [("/1", "type")]
    assert keys(validate_schema(schema, ["a"])) == [("", "minItems")]


def test_instance_path_escaping():
    errs = validate_schema(
        {"type": "object", "properties": {"a/b": {"type": "string"}}}, {"a/b": 1}
    )
    assert errs[0]["instancePath"] == "/a~1b"


def test_js_regex_semantics_are_ascii():
    # JS \w is ASCII-only; Python's default is Unicode-aware.
    currency = {"type": "string", "pattern": "^\\w{3}$"}
    assert validate_schema(currency, "USD") == []
    assert keys(validate_schema(currency, "日本円")) == [("", "pattern")]


def test_multiple_types_and_null():
    schema = {"type": ["string", "null"]}
    assert validate_schema(schema, None) == []
    assert validate_schema(schema, "x") == []
    assert keys(validate_schema(schema, 1)) == [("", "type")]


def test_additional_properties_false_and_pattern_properties():
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "patternProperties": {"^x_": {"type": "number"}},
        "additionalProperties": False,
    }
    assert validate_schema(schema, {"a": "s", "x_1": 2}) == []
    errs = validate_schema(schema, {"nope": 1})
    assert keys(errs) == [("", "additionalProperties")]
    assert errs[0]["params"] == {"additionalProperty": "nope"}


def test_tuple_items_and_additional_items():
    schema = {
        "type": "array",
        "items": [{"type": "string"}, {"type": "number"}],
        "additionalItems": False,
    }
    assert validate_schema(schema, ["a", 1]) == []
    assert keys(validate_schema(schema, ["a", "b"])) == [("/1", "type")]
    assert keys(validate_schema(schema, ["a", 1, 2])) == [("", "additionalItems")]


def test_min_properties():
    assert keys(validate_schema({"type": "object", "minProperties": 1}, {})) == [
        ("", "minProperties")
    ]
