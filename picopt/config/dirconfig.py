"""Resolve per-directory settings from ``.picopt.yaml`` files."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from confuse.exceptions import ConfigError
from loguru import logger
from ruamel.yaml import YAMLError

from picopt.config.consts import DIR_CONFIG_FILENAME

if TYPE_CHECKING:
    from argparse import Namespace
    from pathlib import Path

    from picopt.config import PicoptConfig
    from picopt.config.settings import PicoptSettings
    from picopt.log.summary import Stats


class DirConfig:
    """
    Resolve the effective settings for a directory from ``.picopt.yaml`` files.

    Walks up the tree from a file's directory to the CLI target root
    (``top_path``), collecting the ``.picopt.yaml`` files along the way,
    and layers them beneath env vars and CLI args (via
    :meth:`PicoptConfig.get_dir_settings`). Results are cached per
    directory so cost is O(unique dirs), not O(files), and a fast path
    returns the run-wide settings untouched when no directory config
    applies.
    """

    # Run-mode keys are forced to the run-level values: a per-directory
    # dry_run with run-level timestamps would stamp files that were never
    # optimized, wrong-skipping them forever. Validated in the file per
    # the full-schema decision, but governed at run level.
    _RUN_LEVEL_KEYS = ("dry_run", "list_only")
    # Mid-walk directories additionally pin timestamps: stamp trees are
    # built per top path before the walk, so a subdirectory config cannot
    # toggle stamping mid-tree. The tree root's own config IS honored —
    # see get_tree_settings().
    _MID_WALK_PINNED_KEYS = (*_RUN_LEVEL_KEYS, "timestamps")

    def __init__(
        self,
        picopt_config: PicoptConfig,
        args: Namespace | None,
        global_settings: PicoptSettings,
        stats: Stats | None = None,
    ) -> None:
        """Initialize caches and the resolver dependencies."""
        self._picopt_config: PicoptConfig = picopt_config
        self._args: Namespace | None = args
        self._global_settings: PicoptSettings = global_settings
        self._stats: Stats | None = stats
        # Cache of each directory's readable config file (or None).
        self._dir_config_files: dict[Path, Path | None] = {}
        # Cache of resolved settings keyed by the file's directory.
        self._settings: dict[Path, PicoptSettings] = {}
        # Separate cache for tree-root settings: the same directory's
        # mid-walk settings pin ``timestamps`` and must not collide.
        self._tree_settings: dict[Path, PicoptSettings] = {}
        # Failure reasons already reported, so each is logged only once.
        self._failed: set[str] = set()

    def _dir_config_file(self, path: Path) -> Path | None:
        """Return ``path``'s readable ``.picopt.yaml``, or None. Cached."""
        if path not in self._dir_config_files:
            config_file = path / DIR_CONFIG_FILENAME
            # Use the run-wide symlinks setting to decide whether to read a
            # config file: a file can't be trusted to say whether it should
            # itself be read.
            found = (
                config_file
                if config_file.is_file()
                and (self._global_settings.symlinks or not config_file.is_symlink())
                else None
            )
            self._dir_config_files[path] = found
        return self._dir_config_files[path]

    def _discover(self, top_path: Path, dir_path: Path) -> tuple[Path, ...]:
        """
        Collect ``.picopt.yaml`` files from ``top_path`` down to ``dir_path``.

        Walks UP from ``dir_path`` to ``top_path`` (bounded at the CLI
        target root so nothing above it is read), then reverses so the
        result is shallowest→deepest — the order ``confuse.set_file``
        needs for deeper directories to win.
        """
        files: list[Path] = []
        path = dir_path
        # Check the boundary only after visiting the current dir so
        # top_path's own config applies to nested paths too.
        while True:
            if (config_file := self._dir_config_file(path)) is not None:
                files.append(config_file)
            if path in (top_path, path.parent):
                break
            path = path.parent
        files.reverse()
        return tuple(files)

    def _record_failure(self, dir_files: tuple[Path, ...], exc: Exception) -> None:
        """Log a directory-config failure once per offending file."""
        # confuse names the offending file in its message, and it is stable
        # across descendant directories that re-read the same bad ancestor,
        # so deduping on the reason logs each broken file exactly once.
        reason = str(exc)
        if reason in self._failed:
            return
        self._failed.add(reason)
        # OSError carries the path; confuse/YAML errors put it in the reason.
        config_file = getattr(exc, "filename", None) or dir_files[-1]
        msg = f"Could not read directory config: {reason}"
        logger.error(msg)
        if self._stats is not None:
            self._stats.record_error(config_file, msg)

    def _force_run_level_keys(
        self, settings: PicoptSettings, keys: tuple[str, ...] = _MID_WALK_PINNED_KEYS
    ) -> PicoptSettings:
        """Pin run-mode keys to the run-level values."""
        overrides = {key: getattr(self._global_settings, key) for key in keys}
        return replace(settings, **overrides)

    def get_settings(self, top_path: Path, dir_path: Path) -> PicoptSettings:
        """
        Resolve the effective settings for ``dir_path``.

        Returns the run-wide settings unchanged when no ``.picopt.yaml``
        applies (fast path). Otherwise rebuilds a confuse Configuration
        with the discovered directory files layered beneath env/CLI and
        caches the result per directory. A malformed or unreadable
        directory file is isolated: logged once, recorded in stats, and
        the directory falls back to the run-wide settings so the walk
        continues.
        """
        if (cached := self._settings.get(dir_path)) is not None:
            return cached
        dir_files = self._discover(top_path, dir_path)
        if not dir_files:
            return self._global_settings
        try:
            settings = self._force_run_level_keys(
                self._picopt_config.get_dir_settings(self._args, dir_files)
            )
        except (ConfigError, YAMLError, OSError) as exc:
            self._record_failure(dir_files, exc)
            settings = self._global_settings
        self._settings[dir_path] = settings
        return settings

    def get_tree_settings(self, top_path: Path) -> PicoptSettings:
        """
        Resolve a tree root's effective settings for timestamps purposes.

        Unlike :meth:`get_settings`, the root ``.picopt.yaml`` is honored
        for ``timestamps`` too — only ``dry_run``/``list_only`` stay pinned
        (and they already mask ``timestamps`` off inside the config build).
        CLI and env still win over the file via the normal layering. A file
        target resolves its parent directory's config.
        """
        root_dir = top_path if top_path.is_dir() else top_path.parent
        if (cached := self._tree_settings.get(root_dir)) is None:
            cached = self._resolve_tree_settings(root_dir)
            self._tree_settings[root_dir] = cached
        return cached

    def _resolve_tree_settings(self, root_dir: Path) -> PicoptSettings:
        """Resolve the tree root's own config; fall back like get_settings."""
        dir_files = self._discover(root_dir, root_dir)
        if not dir_files:
            return self._global_settings
        try:
            return self._force_run_level_keys(
                self._picopt_config.get_dir_settings(self._args, dir_files),
                keys=self._RUN_LEVEL_KEYS,
            )
        except (ConfigError, YAMLError, OSError) as exc:
            self._record_failure(dir_files, exc)
            return self._global_settings
