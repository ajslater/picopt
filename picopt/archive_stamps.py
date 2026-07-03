"""Detached, picklable treestamps slice for worker-side archive walks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from treestamps import Treestamps

if TYPE_CHECKING:
    from treestamps.tree.config import TreestampsConfig


class ArchiveStamps:
    """
    Read-only timestamps view an archive's unpack worker can use.

    Grovestamps holds unpicklable ruamel state, so archive handlers carry
    this instead: the tree's config (picklable by design) plus a seed of
    the archive's effective ancestor timestamp. A real, detached
    :class:`Treestamps` is rebuilt lazily in the worker; it is never
    ``set()`` or dumped, so it never opens a WAL or writes to disk. That
    keeps the full treestamps semantics — ancestor-max lookups and
    config-checked loading of ``.picopt_treestamps`` files found inside
    archives — without duplicating them.
    """

    def __init__(self, tree_config: TreestampsConfig, seed: dict[str, Any]) -> None:
        """
        Store the picklable ingredients; defer tree construction.

        ``seed`` is a ``Treestamps.dump_dict()`` mapping: config header
        tags plus relative-path timestamp entries. The header must be
        present (and match) when the config carries ``check_config=True``.
        """
        self._tree_config = tree_config
        self._seed = seed
        self._tree: Treestamps | None = None
        self.filename: str = Treestamps.get_filename(tree_config.program_name)

    def __getstate__(self) -> dict[str, Any]:
        """Drop the lazily built tree; it holds unpicklable ruamel state."""
        state = self.__dict__.copy()
        state["_tree"] = None
        return state

    def _get_tree(self) -> Treestamps:
        if self._tree is None:
            tree = Treestamps(self._tree_config)
            if self._seed:
                tree.load_map(tree.root_dir, self._seed)
            self._tree = tree
        return self._tree

    def get_timestamp(self, top_path: Path, path: Path | str) -> float | None:
        """Grovestamps-compatible ancestor-max timestamp lookup."""
        del top_path  # one tree only; kept for Grovestamps API parity
        return self._get_tree().get(path)

    def loads(self, path: str | Path, yaml_str: str | bytes) -> None:
        """
        Load a timestamps yaml found inside the archive.

        ``path`` is the archive pseudo-path directory the yaml was found
        in; relative entries anchor there. Passed straight to
        ``Treestamps.loads`` (config checking included) — Grovestamps'
        ``is_dir()`` re-anchoring would misfire on pseudo-paths that do
        not exist on the filesystem.
        """
        self._get_tree().loads(Path(path), yaml_str)
