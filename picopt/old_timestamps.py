"""import old picopt timestamps to new ones."""
import os

from pathlib import Path

from treestamps import Treestamps

from picopt import PROGRAM_NAME


_OLD_TIMESTAMPS_NAME = f".{PROGRAM_NAME}_timestamp"


class OldTimestamps:
    """Old timestamps importer."""

    def _add_old_timestamp(self, old_timestamp_path: Path) -> None:
        """Get the timestamp from a old style timestamp file."""
        if not old_timestamp_path.exists():
            return

        path = old_timestamp_path.parent
        mtime = old_timestamp_path.stat().st_mtime
        self._timestamps.set(path, mtime)

    def _import_old_parent_timestamps(self, path: Path) -> None:
        """Walk up to the root eating old style timestamps."""
        old_timestamp_path = path / _OLD_TIMESTAMPS_NAME
        self._add_old_timestamp(old_timestamp_path)
        if path.parent != path:
            self._import_old_parent_timestamps(path.parent)

    def _import_old_child_timestamps(self, path: Path) -> None:
        for root, dirnames, filenames in os.walk(path):
            root_path = Path(root)
            if _OLD_TIMESTAMPS_NAME in filenames:
                old_timestamp_path = root_path / _OLD_TIMESTAMPS_NAME
                self._add_old_timestamp(old_timestamp_path)
                self._timestamps._consumed_paths.add(old_timestamp_path)
            for dirname in dirnames:
                self._import_old_child_timestamps(root_path / dirname)

    def import_old_timestamps(self) -> None:
        """Import all old timestamps."""
        self._import_old_parent_timestamps(self._timestamps.dir)
        self._import_old_child_timestamps(self._timestamps.dir)

    def __init__(self, timestamps: Treestamps):
        """Hold new timestamp object."""
        self._timestamps = timestamps
