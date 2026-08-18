from gbfs_validator.schema.engine import validate_schema


def kws(errs):
    return sorted(e["keyword"] for e in errs)


def test_anyof_reports_branch_errors_plus_summary():
    schema = {"anyOf": [{"type": "string"}, {"type": "number"}]}
    assert kws(validate_schema(schema, True)) == ["anyOf", "type", "type"]
    assert validate_schema(schema, "x") == []


def test_oneof_zero_and_multi_pass():
    schema = {"oneOf": [{"type": "integer"}, {"type": "number"}]}
    errs = validate_schema(schema, 1)
    assert kws(errs) == ["oneOf"]
    assert errs[0]["params"] == {"passingSchemas": [0, 1]}
    assert kws(validate_schema(schema, "x")) == ["oneOf", "type", "type"]


def test_allof_recurses_without_summary():
    schema = {"allOf": [{"required": ["a"]}, {"required": ["b"]}]}
    assert kws(validate_schema(schema, {})) == ["required", "required"]


def test_not():
    assert kws(validate_schema({"not": {"type": "string"}}, "x")) == ["not"]
    assert validate_schema({"not": {"type": "string"}}, 1) == []


def test_if_then_reports_then_errors_and_filterable_if():
    schema = {
        "if": {"properties": {"kind": {"const": "e"}}, "required": ["kind"]},
        "then": {"required": ["range"]},
    }
    errs = validate_schema(schema, {"kind": "e"})
    assert kws(errs) == ["if", "required"]
    ifs = [e for e in errs if e["keyword"] == "if"]
    assert ifs[0]["params"] == {"failingKeyword": "then"}
    assert validate_schema(schema, {"kind": "x"}) == []


def test_if_else_branch():
    schema = {
        "if": {"properties": {"kind": {"const": "e"}}, "required": ["kind"]},
        "else": {"required": ["other"]},
    }
    errs = validate_schema(schema, {"kind": "x"})
    assert kws(errs) == ["if", "required"]
    ifs = [e for e in errs if e["keyword"] == "if"]
    assert ifs[0]["params"] == {"failingKeyword": "else"}


def test_dependencies_property_list():
    schema = {"dependencies": {"a": ["b"]}}
    errs = validate_schema(schema, {"a": 1})
    assert kws(errs) == ["dependencies"]
    assert errs[0]["params"]["missingProperty"] == "b"
    assert validate_schema(schema, {"a": 1, "b": 2}) == []
    assert validate_schema(schema, {}) == []


def test_dependencies_schema_form():
    schema = {"dependencies": {"a": {"required": ["b"]}}}
    assert kws(validate_schema(schema, {"a": 1})) == ["required"]


def test_contains():
    schema = {"type": "array", "contains": {"const": "x"}}
    assert kws(validate_schema(schema, ["a", "b"])) == ["const", "const", "contains"]
    assert validate_schema(schema, ["a", "x"]) == []


def test_error_message_required_map():
    schema = {
        "errorMessage": {"required": {"vehicle_type_id": "custom msg"}},
        "required": ["vehicle_type_id"],
    }
    errs = validate_schema(schema, {})
    assert kws(errs) == ["errorMessage"]
    assert errs[0]["message"] == "custom msg"
    assert errs[0]["keyword"] == "errorMessage"
    inner = errs[0]["params"]["errors"]
    assert inner[0]["keyword"] == "required"


def test_error_message_leaves_unmapped_required_alone():
    schema = {
        "errorMessage": {"required": {"a": "custom"}},
        "required": ["a", "b"],
    }
    errs = validate_schema(schema, {})
    assert kws(errs) == ["errorMessage", "required"]


def test_nested_applicator_schema_paths():
    schema = {"allOf": [{"properties": {"a": {"type": "string"}}}]}
    errs = validate_schema(schema, {"a": 1})
    assert errs[0]["schemaPath"] == "#/allOf/0/properties/a/type"
    assert errs[0]["instancePath"] == "/a"
