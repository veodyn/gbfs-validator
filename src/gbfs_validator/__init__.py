from typing import Any

from gbfs_validator.feed import GBFS
from gbfs_validator.version import __version__


def validate_feed(url: str, **kwargs: Any) -> dict[str, Any]:
    """Validate a GBFS feed and return the report."""
    return GBFS(url, **kwargs).validation()


__all__ = ["GBFS", "__version__", "validate_feed"]
