"""Reading the feed list out of a gbfs.json discovery document.

This runs before gbfs.json has been validated, so it sees whatever the feed
served. Upstream reads it with plain JavaScript member access (gbfs.js:470-486),
which throws on some shapes and quietly yields undefined on others; both
outcomes are part of the parity contract.
"""

from __future__ import annotations

import re
from typing import Any

from gbfs_validator.jsvalues import array, entries, interpolate, member

_V3 = re.compile(r"^3\.\d")


def feed_entries(data: Any, file_type: str, version: Any) -> list[Any]:
    """The discovery entries for one file type, in `getFile`'s two shapes."""
    if _V3.match(interpolate(version)):
        return _v3_feeds(data, file_type)
    return _v2_feeds(data, file_type)


def _v3_feeds(data: Any, file_type: str) -> list[Any]:
    """`data.feeds?.filter((f) => f.name === type) || []`: only `feeds` is
    optional, so a null `data` throws."""
    feeds = member(data, "feeds")
    if feeds is None:
        return []
    return [feed for feed in array(feeds, "data.feeds.filter") if member(feed, "name") == file_type]


def _v2_feeds(data: Any, file_type: str) -> list[dict[str, Any]]:
    """One entry per discovery language, merged with its matching feed. A
    language carrying no `feeds` calls `undefined.find` and throws."""
    found: list[dict[str, Any]] = []
    for lang, language in entries(data, "autoDiscovery.data"):
        feeds = array(member(language, "feeds"), f"data.{lang}.feeds.find")
        match = next((feed for feed in feeds if member(feed, "name") == file_type), None)
        found.append({"lang": lang, **(match or {})})
    return found
