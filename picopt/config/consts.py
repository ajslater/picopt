"""
Config constants.

Almost everything that used to live in this file (ALL_FORMAT_STRS,
CONVERT_TO_FORMAT_STRS, DEFAULT_HANDLERS, ARCHIVE_CONVERT_FROM_FORMAT_STRS,
CB_CONVERT_FROM_FORMAT_STRS, etc) is now a registry query — see
:mod:`picopt.plugins`. The only thing left is the timestamps config-key
allowlist, which doesn't depend on the format registry at all.
"""

from typing import Final

# Per-directory config files layer beneath env vars and CLI args but above
# the user config. Named to be distinct from the timestamps file
# ``.picopt_treestamps.yaml``. Lives here (a leaf module) so the walk layer
# can import it without triggering the config package's heavy import chain.
DIR_CONFIG_FILENAME: Final = ".picopt.yaml"

TIMESTAMPS_CONFIG_KEYS: Final[frozenset[str]] = frozenset(
    {
        "bigger",
        # These change which files are converted, so they must invalidate
        # stamps for the same reason convert_to does.
        "convert_jpeg_to_jxl",
        "convert_to",
        "convert_webp_to_jxl",
        "formats",
        "ignore",
        "keep_metadata",
        "near_lossless",
        "recurse",
        "symlinks",
        # Changes which archive members are optimized, so flipping it must
        # invalidate stamps like any other behavior-affecting option.
        "timestamps_ignore_archive_entry_mtimes",
    }
)
