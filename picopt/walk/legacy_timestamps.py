"""import picopt 2.0 timestamps to Treestamps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from picopt.path import is_path_case_sensitive, is_path_ignored

if TYPE_CHECKING:
    from pathlib import Path

    from treestamps import Treestamps

    from picopt.config.settings import PicoptSettings

OLD_TIMESTAMPS_NAME = ".picopt_timestamp"


class OldTimestamps:
    """Old timestamps importer."""

    def _add_old_timestamp(self, old_timestamp_path: Path) -> None:
        """Get the timestamp from a old style timestamp file."""
        if not old_timestamp_path.exists():
            return

        path = old_timestamp_path.parent
        mtime = old_timestamp_path.stat().st_mtime
        self._timestamps.set(path, mtime)

    def _import_old_parent_timestamps(self) -> None:
        """Walk up to the root eating old style timestamps."""
        path = self._root_dir
        while path:
            if is_path_ignored(self._config, path, ignore_case=self._ignore_case) or (
                not self._config.symlinks and path.is_symlink()
            ):
                return
            old_timestamp_path = path / OLD_TIMESTAMPS_NAME
            self._add_old_timestamp(old_timestamp_path)
            path = False if path.parent == path else path.parent

    def _import_old_child_timestamps(self) -> None:
        stack = [self._root_dir]
        visited: set[tuple[int, int]] = set()
        while stack:
            path = stack.pop()
            try:
                if not self._config.symlinks and path.is_symlink():
                    continue
                if path.is_dir():
                    # Symlink cycles must not walk forever.
                    dir_stat = path.stat()
                    dir_key = (dir_stat.st_dev, dir_stat.st_ino)
                    if dir_key in visited:
                        continue
                    visited.add(dir_key)
                    if not is_path_ignored(
                        self._config, path, ignore_case=self._ignore_case
                    ):
                        stack.extend(path.iterdir())
                elif path.name == OLD_TIMESTAMPS_NAME:
                    self._add_old_timestamp(path)
                    # consume child timestamps
                    self._timestamps._consumed_paths.add(path)  # noqa: SLF001
            except OSError as exc:
                # An unreadable directory is not worth aborting the run.
                logger.warning(f"Legacy timestamp import skipping {path}: {exc}")

    def import_old_timestamps(self) -> None:
        """Import all old timestamps."""
        self._import_old_parent_timestamps()
        self._import_old_child_timestamps()

    def __init__(self, config: PicoptSettings, timestamps: Treestamps) -> None:
        """Hold new timestamp object."""
        self._config: PicoptSettings = config
        self._timestamps: Treestamps = timestamps
        self._root_dir: Path = self._timestamps.root_dir
        # Ignore patterns match case-insensitively only on filesystems
        # that are themselves case-insensitive.
        self._ignore_case: bool = not is_path_case_sensitive(self._root_dir)
