"""
Config constants.

Almost everything that used to live in this file (ALL_FORMAT_STRS,
CONVERT_TO_FORMAT_STRS, DEFAULT_HANDLERS, ARCHIVE_CONVERT_FROM_FORMAT_STRS,
CB_CONVERT_FROM_FORMAT_STRS, etc) is now a registry query — see
:mod:`picopt.plugins`. The only thing left is the timestamps config-key
allowlist, which doesn't depend on the format registry at all.
"""

from collections.abc import Mapping
from importlib.resources import files
from types import MappingProxyType
from typing import Any, Final

from ruamel.yaml import YAML

from picopt import PROGRAM_NAME

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


def _packaged_defaults() -> Mapping[str, Any]:
    """Load the packaged default config values."""
    text = (files(PROGRAM_NAME) / "config_default.yaml").read_text()
    return YAML(typ="safe").load(text)[PROGRAM_NAME]


# Treestamps fills keys missing from either side of a config comparison
# from these before diffing, so adding or retiring a recorded key does not
# invalidate stamp files written before the change. A KeyError here is a
# deliberate import-time guard: every recorded key needs a packaged default.
TIMESTAMPS_CONFIG_DEFAULTS: Final[Mapping[str, Any]] = MappingProxyType(
    {key: _packaged_defaults()[key] for key in TIMESTAMPS_CONFIG_KEYS}
)

# When a key leaves TIMESTAMPS_CONFIG_KEYS, move its last packaged default
# here: stamp files that recorded it at its default stay valid, while ones
# that recorded another value still invalidate. Keys *added* to
# TIMESTAMPS_CONFIG_KEYS must default to behavior-preserving values,
# because a key missing from an old stamp file reads as the current default.
RETIRED_TIMESTAMPS_CONFIG_DEFAULTS: Final[Mapping[str, Any]] = MappingProxyType({})
