"""
Config constants.

Almost everything that used to live in this file (ALL_FORMAT_STRS,
CONVERT_TO_FORMAT_STRS, DEFAULT_HANDLERS, ARCHIVE_CONVERT_FROM_FORMAT_STRS,
CB_CONVERT_FROM_FORMAT_STRS, etc) is now a registry query — see
:mod:`picopt.plugins`. The only thing left is the timestamps config-key
allowlist, which doesn't depend on the format registry at all.
"""

from typing import Final

TIMESTAMPS_CONFIG_KEYS: Final[frozenset[str]] = frozenset(
    {
        "bigger",
        "convert_to",
        "formats",
        "ignore",
        "keep_metadata",
        "near_lossless",
        "recurse",
        "symlinks",
    }
)
