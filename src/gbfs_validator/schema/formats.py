"""Port of ajv-formats 2.1.1 "full" mode for the four formats GBFS schemas use."""

import re
from collections.abc import Callable

# Regex sources are verbatim from ajv-formats dist/formats.js, with the trailing
# `$` written as `\Z` because Python's `$` also matches before a final newline.
# re.ASCII keeps `\d` and case folding ASCII-only, as JS regexes are.
_URI = re.compile(
    r"^(?:[a-z][a-z0-9+\-.]*:)(?:\/?\/(?:(?:[a-z0-9\-._~!$&'()*+,;=:]|%[0-9a-f]{2})*@)?(?:\[(?:(?:(?:(?:[0-9a-f]{1,4}:){6}|::(?:[0-9a-f]{1,4}:){5}|(?:[0-9a-f]{1,4})?::(?:[0-9a-f]{1,4}:){4}|(?:(?:[0-9a-f]{1,4}:){0,1}[0-9a-f]{1,4})?::(?:[0-9a-f]{1,4}:){3}|(?:(?:[0-9a-f]{1,4}:){0,2}[0-9a-f]{1,4})?::(?:[0-9a-f]{1,4}:){2}|(?:(?:[0-9a-f]{1,4}:){0,3}[0-9a-f]{1,4})?::[0-9a-f]{1,4}:|(?:(?:[0-9a-f]{1,4}:){0,4}[0-9a-f]{1,4})?::)(?:[0-9a-f]{1,4}:[0-9a-f]{1,4}|(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?))|(?:(?:[0-9a-f]{1,4}:){0,5}[0-9a-f]{1,4})?::[0-9a-f]{1,4}|(?:(?:[0-9a-f]{1,4}:){0,6}[0-9a-f]{1,4})?::)|[Vv][0-9a-f]+\.[a-z0-9\-._~!$&'()*+,;=:]+)\]|(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)|(?:[a-z0-9\-._~!$&'()*+,;=]|%[0-9a-f]{2})*)(?::\d*)?(?:\/(?:[a-z0-9\-._~!$&'()*+,;=:@]|%[0-9a-f]{2})*)*|\/(?:(?:[a-z0-9\-._~!$&'()*+,;=:@]|%[0-9a-f]{2})+(?:\/(?:[a-z0-9\-._~!$&'()*+,;=:@]|%[0-9a-f]{2})*)*)?|(?:[a-z0-9\-._~!$&'()*+,;=:@]|%[0-9a-f]{2})+(?:\/(?:[a-z0-9\-._~!$&'()*+,;=:@]|%[0-9a-f]{2})*)*)(?:\?(?:[a-z0-9\-._~!$&'()*+,;=:@/?]|%[0-9a-f]{2})*)?(?:#(?:[a-z0-9\-._~!$&'()*+,;=:@/?]|%[0-9a-f]{2})*)?\Z",
    re.IGNORECASE | re.ASCII,
)
_NOT_URI_FRAGMENT = re.compile(r"\/|:")
_EMAIL = re.compile(
    r"^[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\Z",
    re.IGNORECASE | re.ASCII,
)
_DATE = re.compile(r"^(\d\d\d\d)-(\d\d)-(\d\d)\Z", re.ASCII)
_TIME = re.compile(
    r"^(\d\d):(\d\d):(\d\d)(\.\d+)?(z|[+-]\d\d(?::?\d\d)?)?\Z", re.IGNORECASE | re.ASCII
)
# The codepoints JS `\s` matches; Python's `\s` omits U+FEFF and adds U+001C-U+001F, U+0085.
_JS_SPACE = "".join(
    chr(c)
    for c in (
        0x09,
        0x0A,
        0x0B,
        0x0C,
        0x0D,
        0x20,
        0xA0,
        0x1680,
        *range(0x2000, 0x200B),
        0x2028,
        0x2029,
        0x202F,
        0x205F,
        0x3000,
        0xFEFF,
    )
)
_DATE_TIME_SEPARATOR = re.compile("t|[" + re.escape(_JS_SPACE) + "]", re.IGNORECASE)
_DAYS = (0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _date(value: str) -> bool:
    matches = _DATE.match(value)
    if not matches:
        return False
    year, month, day = int(matches[1]), int(matches[2]), int(matches[3])
    if not 1 <= month <= 12:
        return False
    limit = 29 if month == 2 and _is_leap_year(year) else _DAYS[month]
    return 1 <= day <= limit


def _time(value: str, with_time_zone: bool) -> bool:
    matches = _TIME.match(value)
    if not matches:
        return False
    hour, minute, second = int(matches[1]), int(matches[2]), int(matches[3])
    time_zone = matches[5]
    in_range = (hour <= 23 and minute <= 59 and second <= 59) or (
        hour == 23 and minute == 59 and second == 60
    )
    # ajv-formats compares an absent timezone (undefined) to "", so this never
    # rejects; None != "" reproduces that.
    return in_range and (not with_time_zone or time_zone != "")


def _date_time(value: str) -> bool:
    parts = _DATE_TIME_SEPARATOR.split(value)
    return len(parts) == 2 and _date(parts[0]) and _time(parts[1], True)


def _uri(value: str) -> bool:
    return _NOT_URI_FRAGMENT.search(value) is not None and _URI.match(value) is not None


def _email(value: str) -> bool:
    return _EMAIL.match(value) is not None


FORMATS: dict[str, Callable[[str], bool]] = {
    "uri": _uri,
    "email": _email,
    "date": _date,
    "date-time": _date_time,
}
