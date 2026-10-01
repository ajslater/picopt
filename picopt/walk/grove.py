"""Per-tree timestamp stores keyed by top path."""

from __future__ import annotations

from functools import partial
from hashlib import sha256
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from treestamps import (
    Grovestamps,
    GrovestampsConfig,
    Treestamps,
    TreestampsConfig,
    dir_config_fingerprint,
)
from typing_extensions import override

from picopt import PROGRAM_NAME
from picopt.config.consts import (
    DIR_CONFIG_FILENAME,
    RETIRED_TIMESTAMPS_CONFIG_DEFAULTS,
    TIMESTAMPS_CONFIG_DEFAULTS,
    TIMESTAMPS_CONFIG_KEYS,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

    from picopt.config.dirconfig import DirConfig
    from picopt.config.settings import PicoptSettings

_FINGERPRINT_KEY: Final = "_dir_config_fingerprint"
_PROGRAM_CONFIG_KEYS: Final = TIMESTAMPS_CONFIG_KEYS | {_FINGERPRINT_KEY}
# A tree with no sub-directory config files hashes to the empty digest, so
# that is the default for stamp files written before the key existed.
_EMPTY_FINGERPRINT: Final = sha256(b"").hexdigest()
_PROGRAM_CONFIG_DEFAULTS: Final[Mapping[str, Any]] = MappingProxyType(
    {
        **TIMESTAMPS_CONFIG_DEFAULTS,
        **RETIRED_TIMESTAMPS_CONFIG_DEFAULTS,
        _FINGERPRINT_KEY: _EMPTY_FINGERPRINT,
    }
)
_KEY_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {_FINGERPRINT_KEY: f"sub-directory {DIR_CONFIG_FILENAME} contents"}
)
_NOTE: Final = ("Safe to delete: picopt will re-optimize this tree on the next run.",)


def _dir_config_fingerprint(root_dir: Path) -> str:
    """
    Hash the option values of every config file strictly below the root.

    The root's own config file is excluded: its options are already
    recorded as values in the tree's program config, so only configs the
    recorded values can't see — those in subdirectories — need the digest.
    """
    return dir_config_fingerprint(root_dir, DIR_CONFIG_FILENAME, PROGRAM_NAME)


def _tree_config(
    top_path: Path, *, dirconfig: DirConfig, run_config: PicoptSettings
) -> TreestampsConfig | None:
    """
    Build a tree's config from its root's resolved settings.

    Returns None — no store, no stamp file — when those settings disable
    timestamps or exclude the symlinked top path.
    """
    resolved = dirconfig.get_tree_settings(top_path)
    if not resolved.timestamps:
        return None
    if not resolved.symlinks and top_path.is_symlink():
        return None
    program_config: dict[str, Any] = {
        config_key: getattr(resolved, config_key)
        for config_key in TIMESTAMPS_CONFIG_KEYS
    }
    root_dir = Treestamps.get_dir(top_path).absolute()
    program_config[_FINGERPRINT_KEY] = _dir_config_fingerprint(root_dir)
    return TreestampsConfig(
        program_name=PROGRAM_NAME,
        path=top_path,
        verbose=run_config.verbose,
        symlinks=resolved.symlinks,
        ignore=resolved.ignore,
        check_config=resolved.timestamps_check_config,
        # Plain dicts so CommonConfig.__post_init__ filters & normalizes.
        program_config=program_config,
        program_config_keys=_PROGRAM_CONFIG_KEYS,
        program_config_defaults=dict(_PROGRAM_CONFIG_DEFAULTS),
        program_config_key_labels=_KEY_LABELS,
        note=_NOTE,
    )


class Grove(Grovestamps):
    """
    One Treestamps per stamp-active top path, keyed by tree root.

    Each tree records the settings that actually govern it — the tree
    root's resolved ``.picopt.yaml`` layered beneath CLI/env — plus a
    fingerprint of the sub-directory configs those values can't see. A
    tree whose resolved root settings disable timestamps gets no store at
    all.

    Lookup asymmetry: ``__getitem__`` raises KeyError for unknown top
    paths (handler_factory relies on it to mean "no stamps for this
    tree"), while ``set()`` and ``get_timestamp()`` tolerate them —
    stamp-inactive trees coexist with active ones in the same walk.
    """

    def __init__(
        self,
        top_paths: Iterable[Path],
        dirconfig: DirConfig,
        run_config: PicoptSettings,
    ) -> None:
        """Build one loaded Treestamps per stamp-active top path."""
        config = GrovestampsConfig(
            program_name=PROGRAM_NAME,
            paths=top_paths,
            # Keep every top path: the factory drops symlinked ones by
            # each tree's resolved setting, not the run-level one.
            symlinks=True,
            tree_config_factory=partial(
                _tree_config, dirconfig=dirconfig, run_config=run_config
            ),
        )
        super().__init__(config)

    @override
    def set(
        self,
        top_path: Path,
        path: Path,
        mtime: float | None = None,
        *,
        compact: bool = False,
    ) -> None:
        """Set a timestamp in the tree; no-op for stamp-inactive trees."""
        if (tree := self.get(top_path)) is not None:
            tree.set(path, mtime, compact=compact)

    @override
    def get_timestamp(self, top_path: Path, path: Path | str) -> float | None:
        """Get a timestamp from the tree; None for stamp-inactive trees."""
        if (tree := self.get(top_path)) is not None:
            return tree.get(path)
        return None
