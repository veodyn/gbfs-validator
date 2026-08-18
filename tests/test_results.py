from gbfs_validator.results import count_errors, file_has_errors, files_have_errors, has_errors


def test_missing_required_file_counts_one():
    assert count_errors({"required": True, "exists": False}) == 1


def test_file_level_errors_list_length_wins():
    f = {"required": True, "exists": True, "hasErrors": True, "errors": [1, 2, 3]}
    assert count_errors(f) == 3


def test_language_counting():
    f = {
        "required": True,
        "exists": False,
        "hasErrors": True,
        "languages": [
            {"exists": True, "errors": [1, 2]},
            {"exists": False, "errors": []},
        ],
    }
    # 1 for the missing required file + 1 missing language + 2 errors
    assert count_errors(f) == 4


def test_language_missing_not_counted_when_optional():
    f = {
        "required": False,
        "exists": False,
        "hasErrors": True,
        "languages": [{"exists": False, "errors": []}],
    }
    assert count_errors(f) == 0


def test_has_errors_required_and_missing():
    assert has_errors({"exists": False}, True) is True
    assert has_errors({"exists": False, "errors": False, "hasErrors": False}, False) is False
    assert has_errors({"exists": True, "errors": [1]}, False) is True


def test_files_have_errors():
    assert (
        files_have_errors([{"required": True, "exists": True, "errors": False, "hasErrors": False}])
        is False
    )
    assert files_have_errors([{"required": True, "exists": False}]) is True


def test_multi_language_empty_and_required():
    assert file_has_errors([], True) is True
    assert file_has_errors([], False) is False


# --- extra branch coverage of the four upstream functions --------------------


def test_has_errors_missing_file_data_when_required():
    assert has_errors(None, True) is True
    assert has_errors({}, True) is True


def test_has_errors_empty_error_list_is_truthy_by_js_rules():
    # gbfs.js:71 tests `!!fileData.errors`, and `!![]` is true in JS even though bool([]) is False.
    assert has_errors({"exists": True, "errors": [], "hasErrors": False}, True) is True
    assert has_errors({"exists": True, "errors": False, "hasErrors": False}, True) is False
    assert has_errors({"exists": True, "hasErrors": False}, True) is False
    assert has_errors({"exists": True, "errors": None, "hasErrors": False}, True) is False


def test_has_errors_flag_alone_is_enough():
    assert has_errors({"exists": True, "errors": False, "hasErrors": True}, True) is True


def test_has_errors_ignores_missing_file_when_optional():
    assert has_errors({"exists": False}, False) is False


def test_file_has_errors_non_list_delegates():
    assert file_has_errors({"exists": True, "errors": [1]}, False) is True
    assert file_has_errors({"exists": True, "errors": False, "hasErrors": False}, True) is False
    assert file_has_errors({"exists": False}, True) is True


def test_file_has_errors_multi_language():
    clean = {"exists": True, "errors": False, "hasErrors": False}
    dirty = {"exists": True, "errors": [1], "hasErrors": True}
    assert file_has_errors([clean, clean], True) is False
    assert file_has_errors([clean, dirty], True) is True
    # a missing language only counts when the file is required
    assert file_has_errors([clean, {"exists": False, "errors": False}], True) is True
    assert file_has_errors([clean, {"exists": False, "errors": False}], False) is False


def test_files_have_errors_non_list_is_no_error():
    assert files_have_errors({"required": True, "exists": False}) is False
    assert files_have_errors(None) is False
    assert files_have_errors([]) is False


def test_files_have_errors_uses_each_files_required_flag():
    assert files_have_errors([{"required": False, "exists": False}]) is False
    assert (
        files_have_errors(
            [
                {"required": True, "exists": True, "errors": False, "hasErrors": False},
                {"required": False, "exists": True, "hasErrors": True},
            ]
        )
        is True
    )


def test_count_errors_no_errors_at_all():
    assert count_errors({"required": True, "exists": True, "hasErrors": False}) == 0
    assert count_errors({}) == 0


def test_count_errors_missing_file_not_counted_when_optional():
    assert count_errors({"required": False, "exists": False, "hasErrors": False}) == 0


def test_count_errors_error_list_replaces_the_missing_file_count():
    # gbfs.js:101 assigns, so the missing-required +1 is dropped when errors exist.
    f = {"required": True, "exists": False, "hasErrors": True, "errors": [1, 2]}
    assert count_errors(f) == 2


def test_count_errors_empty_error_list_assigns_zero_by_js_rules():
    # gbfs.js:100 takes the `file.errors` branch for [], assigning 0 and skipping languages.
    f = {
        "required": True,
        "exists": False,
        "hasErrors": True,
        "errors": [],
        "languages": [{"exists": True, "errors": [1]}],
    }
    assert count_errors(f) == 0


def test_count_errors_falls_through_to_languages_only_when_errors_is_false_or_absent():
    languages = [{"exists": True, "errors": [1]}]
    base = {"required": True, "exists": True, "hasErrors": True, "languages": languages}
    assert count_errors({**base, "errors": False}) == 1
    assert count_errors({**base, "errors": None}) == 1
    assert count_errors(base) == 1


def test_count_errors_has_errors_without_errors_or_languages():
    assert count_errors({"required": True, "exists": False, "hasErrors": True}) == 1
    assert count_errors({"required": True, "exists": True, "hasErrors": True}) == 0


def test_count_errors_ignores_errors_of_missing_languages():
    f = {
        "required": False,
        "exists": False,
        "hasErrors": True,
        "languages": [{"exists": False, "errors": [1, 2, 3]}, {"exists": True, "errors": [1]}],
    }
    assert count_errors(f) == 1


def test_count_errors_empty_language_list():
    # `[]` is truthy in JS, so upstream enters the languages branch and adds nothing.
    f = {"required": True, "exists": False, "hasErrors": True, "languages": []}
    assert count_errors(f) == 1


def test_count_errors_mirrors_upstream_nan_for_valid_language():
    # gbfs.js:109 sums `false.length`, so the count is NaN, which JSON.stringify emits as null.
    f = {
        "required": True,
        "exists": True,
        "hasErrors": True,
        "languages": [{"exists": True, "errors": False}, {"exists": True, "errors": [1, 2]}],
    }
    assert count_errors(f) is None


def test_count_errors_nan_wins_over_every_other_term():
    f = {
        "required": True,
        "exists": False,
        "hasErrors": True,
        "languages": [
            {"exists": True, "errors": [1, 2]},
            {"exists": False, "errors": []},
            {"exists": True},
        ],
    }
    assert count_errors(f) is None


def test_count_errors_missing_language_without_errors_key_is_not_nan():
    f = {
        "required": True,
        "exists": True,
        "hasErrors": True,
        "languages": [{"exists": False}, {"exists": True, "errors": [1]}],
    }
    # 1 for the missing required language + 1 error; the absent `errors` key is never read.
    assert count_errors(f) == 2
