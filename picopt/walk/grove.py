"""Per-tree timestamp stores keyed by top path."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from treestamps import Treestamps, TreestampsConfig, dir_config_fingerprint
from typing_extensions import override

from picopt import PROGRAM_NAME
from picopt.config.consts import (
    DIR_CONFIG_FILENAME,
    RETIRED_TIMESTAMPS_CONFIG_DEFAULTS,
    TIMESTAMPS_CONFIG_DEFAULTS,
    TIMESTAMPS_CONFIG_KEYS,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

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


class Grove(Mapping[Path, Treestamps]):
    """
    One Treestamps per stamp-active top path, keyed by tree root.

    Replaces treestamps' Grovestamps, whose GrovestampsConfig shares a
    single program_config across all trees. Each tree here records the
    settings that actually govern it — the tree root's resolved
    ``.picopt.yaml`` layered beneath CLI/env — plus a fingerprint of the
    sub-directory configs those values can't see. A tree whose resolved
    root settings disable timestamps gets no store at all.

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
        self._trees: dict[Path, Treestamps] = {}
        # Directory targets before file targets, so a dir target and a
        # file target sharing a root create the recursing dir tree.
        dirs = sorted(path for path in top_paths if path.is_dir())
        files = sorted(path for path in top_paths if not path.is_dir())
        for top_path in (*dirs, *files):
            self._add_tree(top_path, dirconfig, run_config)

    @staticmethod
    def _tree_key(path: Path) -> Path:
        """Normalize a top path the way Treestamps computes its root_dir."""
        return Treestamps.get_dir(path).absolute()

    def _add_tree(
        self, top_path: Path, dirconfig: DirConfig, run_config: PicoptSettings
    ) -> None:
        key = self._tree_key(top_path)
        if key in self._trees:
            return
        resolved = dirconfig.get_tree_settings(top_path)
        if not resolved.timestamps:
            return
        if not resolved.symlinks and top_path.is_symlink():
            return
        program_config: dict[str, Any] = {
            config_key: getattr(resolved, config_key)
            for config_key in TIMESTAMPS_CONFIG_KEYS
        }
        program_config[_FINGERPRINT_KEY] = _dir_config_fingerprint(key)
        config = TreestampsConfig(
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
        tree = Treestamps(config)
        tree.loadf_tree()
        self._trees[key] = tree

    @override
    def __getitem__(self, key: Path) -> Treestamps:
        """Get a Treestamps by its root path; KeyError if stamp-inactive."""
        return self._trees[self._tree_key(key)]

    @override
    def __iter__(self) -> Iterator[Path]:
        """Iterate over tree root paths."""
        return iter(self._trees)

    @override
    def __len__(self) -> int:
        """Return the number of stamp-active trees."""
        return len(self._trees)

    def dumpf(self) -> tuple[Path, ...]:
        """Dump all trees to disk; return the roots that actually wrote."""
        return tuple(sorted(path for path, tree in self._trees.items() if tree.dumpf()))

    def set(
        self,
        top_path: Path,
        path: Path,
        mtime: float | None = None,
        *,
        compact: bool = False,
    ) -> None:
        """Set a timestamp in the tree; no-op for stamp-inactive trees."""
        if (tree := self._trees.get(self._tree_key(top_path))) is not None:
            tree.set(path, mtime, compact=compact)

    def get_timestamp(self, top_path: Path, path: Path | str) -> float | None:
        """Get a timestamp from the tree; None for stamp-inactive trees."""
        if (tree := self._trees.get(self._tree_key(top_path))) is not None:
            return tree.get(path)
        return None
