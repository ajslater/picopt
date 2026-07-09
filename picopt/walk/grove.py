"""Per-tree timestamp stores keyed by top path."""

from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import suppress
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from ruamel.yaml import YAML, YAMLError
from treestamps import Treestamps, TreestampsConfig
from typing_extensions import override

from picopt import PROGRAM_NAME
from picopt.config.consts import DIR_CONFIG_FILENAME, TIMESTAMPS_CONFIG_KEYS

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from picopt.config.dirconfig import DirConfig
    from picopt.config.settings import PicoptSettings

_FINGERPRINT_KEY: Final = "_dir_config_fingerprint"
_PROGRAM_CONFIG_KEYS: Final = TIMESTAMPS_CONFIG_KEYS | {_FINGERPRINT_KEY}


def _canonical_json(value: Any) -> str:
    """Serialize a canonical value deterministically."""
    return json.dumps(value, sort_keys=True, default=str)


def _canonical(value: Any) -> Any:
    """Convert parsed yaml values to a JSON-representable canonical form."""
    if isinstance(value, Mapping):
        return {str(key): _canonical(sub) for key, sub in value.items()}
    if isinstance(value, list | tuple):
        return [_canonical(sub) for sub in value]
    if isinstance(value, set | frozenset):
        # Sort by serialized form: key=str would tie 1 with "1" and leave
        # the order at the mercy of the process hash seed.
        return sorted((_canonical(sub) for sub in value), key=_canonical_json)
    return value


def _config_values_chunk(root: Path, config_file: Path) -> bytes | None:
    """
    Return one config file's fingerprint contribution, or None.

    The contribution is the file's parsed, canonicalized ``picopt:``
    section — so comment, whitespace, and key-order edits don't change
    the digest, only option values do. Unparseable files (including
    pathological yaml that exhausts the recursion limit) contribute
    their raw bytes instead (conservative: any edit invalidates).
    """
    try:
        data = config_file.read_bytes()
    except OSError:
        # Covers missing files and directories named like the config.
        return None
    try:
        parsed = YAML(typ="safe").load(data)
        section = parsed.get(PROGRAM_NAME) if isinstance(parsed, dict) else None
        payload = _canonical_json(_canonical(section)).encode()
    except (YAMLError, RecursionError):
        # RecursionError: recursive anchors survive safe-load as
        # self-referential dicts, and deep flow nesting blows the
        # composer before it can raise a YAMLError.
        payload = data
    # A path relative to the tree root keeps the digest stable across
    # cwd/mount changes; add/remove/rename still flips it. Digesting the
    # payload gives fixed-length framing: raw-byte payloads could
    # otherwise embed NULs that forge chunk boundaries.
    rel = config_file.relative_to(root)
    return str(rel).encode() + b"\0" + sha256(payload).digest()


def _dir_config_fingerprint(root_dir: Path) -> str:
    """
    Hash the option values of every ``.picopt.yaml`` strictly below the root.

    The root's own config file is excluded: its options are already
    recorded as values in the tree's program config, so only configs the
    recorded values can't see — those in subdirectories — need the digest.
    Editing, adding, or removing any of them flips it and the tree
    re-processes on the next run: over-invalidation that is always safe
    and never wrong-skips a file whose effective config changed. A tree
    rooted at a file shares its stamp file with directory runs of the
    same root dir, so both hash identically to keep them from
    invalidating each other.
    """
    hasher = sha256()
    own_config = root_dir / DIR_CONFIG_FILENAME
    candidates = []
    # Collect incrementally: a mid-scan OSError (py<3.13 propagates
    # non-permission errors) keeps what was found instead of degrading
    # to the empty — most permissive — digest.
    with suppress(OSError):
        candidates.extend(
            config_file
            for config_file in root_dir.rglob(DIR_CONFIG_FILENAME)
            if config_file != own_config
        )
    for config_file in sorted(candidates):
        if (chunk := _config_values_chunk(root_dir, config_file)) is not None:
            hasher.update(chunk)
    return hasher.hexdigest()


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
            # Plain dict so CommonConfig.__post_init__ filters & normalizes.
            program_config=program_config,
            program_config_keys=_PROGRAM_CONFIG_KEYS,
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
