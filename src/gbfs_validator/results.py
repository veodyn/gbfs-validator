"""Error-counting helpers ported from upstream gbfs.js."""

from typing import Any

from gbfs_validator.jstruth import truthy as _truthy


def has_errors(file_data: dict[str, Any] | None, required: bool) -> bool:
    """True if a single (non multi-language) file result has errors or is required and missing."""
    if required and (not file_data or not _truthy(file_data.get("exists"))):
        return True
    if file_data is None:
        return False
    return _truthy(file_data.get("errors")) or _truthy(file_data.get("hasErrors"))


def file_has_errors(file_data: Any, required: bool) -> bool:
    """True if a file result has errors; the result may be a per-language list."""
    if isinstance(file_data, list):
        if not file_data and required:
            return True
        return any(has_errors(language_body, required) for language_body in file_data)
    return has_errors(file_data, required)


def files_have_errors(files: Any) -> bool:
    """True if any file result in the list has errors, using each file's own `required` flag."""
    if isinstance(files, list):
        return any(has_errors(file, _truthy(file.get("required"))) for file in files)
    return False


def count_errors(file: dict[str, Any]) -> int | None:
    """Number of errors in one file result, counting a missing required file as one.

    Returns None where upstream's arithmetic yields NaN, which JSON.stringify emits as null.
    """
    count = 0
    if _truthy(file.get("required")) and not _truthy(file.get("exists")):
        count += 1

    if _truthy(file.get("hasErrors")):
        errors: Any = file.get("errors")
        languages: Any = file.get("languages")
        if _truthy(errors):
            # Upstream assigns here, so the missing-required count above is dropped.
            count = len(errors)
        elif _truthy(languages):
            if _truthy(file.get("required")):
                count += sum(1 for language in languages if not _truthy(language.get("exists")))
            for language in languages:
                if not _truthy(language.get("exists")):
                    continue
                language_errors = language.get("errors")
                if not isinstance(language_errors, list):
                    # Mirrors gbfs.js:109, where `false.length` is undefined so the sum goes NaN.
                    return None
                count += len(language_errors)

    return count


def total_errors_count(files: list[dict[str, Any]]) -> int | None:
    """Upstream sums with `+=`, so a single NaN poisons the total (gbfs.js:855)."""
    total = 0
    for file in files:
        count = file.get("errorsCount")
        if count is None:
            return None
        total += count
    return total
