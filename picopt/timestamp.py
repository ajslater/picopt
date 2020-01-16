"""Timestamp writer for keeping track of bulk optimizations."""
from datetime import datetime
from pathlib import Path
from typing import Dict
from typing import Optional
from typing import Set
from typing import Tuple

from . import PROGRAM_NAME
from .settings import Settings


RECORD_FILENAME = f".{PROGRAM_NAME}_timestamp"
_REASON_DEFAULT = ""
_REASON_SYMLINK = "Not setting timestamp because not following symlinks"
_REASON_NONDIR = "Not setting timestamp for a non-directory"


class Timestamp(object):
    """Timestamp object to hold settings and caches."""

    def __init__(self, settings: Settings) -> None:
        """Initialize instance variables."""
        self._settings = settings
        self._timestamp_cache: Dict[Path, Optional[float]] = {}
        self._old_timestamps: Set[Path] = set()

    def _get_timestamp(self, path: Path, remove: bool) -> Optional[float]:
        """
        Get the timestamp from the timestamp file.

        Optionally mark it for removal if we're going to write another one.
        """
        record_path = path / RECORD_FILENAME
        if self._settings.verbose > 1:
            print("looking for", record_path)
        if not record_path.exists():
            return None

        mtime = record_path.stat().st_mtime
        mtime_str = datetime.fromtimestamp(mtime)
        print(f"Found timestamp {path}:{mtime_str}")
        if self._settings.record_timestamp and remove:
            self._old_timestamps.add(record_path)
        return mtime

    def _get_timestamp_cached(self, path: Path, remove: bool) -> Optional[float]:
        """
        Get the timestamp from the cache or fill the cache.

        Much quicker than reading the same files over and over
        """
        if path not in self._timestamp_cache:
            mtime = self._get_timestamp(path, remove)
            self._timestamp_cache[path] = mtime
        return self._timestamp_cache[path]

    def _remove_old_timestamps(
        self, full_path: Path, record_filepath: Path
    ) -> Dict[Path, Optional[OSError]]:
        """Remove old timestamps after setting a new one."""
        removed: Dict[Path, Optional[OSError]] = {}
        for path in self._old_timestamps:
            # only remove timestamps below the curent path
            # but don't remove the timestamp we just set!
            if (
                not path.exists()
                or full_path not in path.parents
                or path.samefile(record_filepath)
            ):
                continue
            try:
                path.unlink()
                removed[path] = None
            except OSError as err:
                removed[path] = err

        if not self._settings.verbose:
            return removed

        for path, error in removed.items():
            if error is None:
                print(f"Removed old timestamp: {path}")
            else:
                print(f"Could not remove old timestamp: {path}: {error.strerror}")

        return removed

    @staticmethod
    def max_none(lst: Tuple[Optional[float], Optional[float]]) -> Optional[float]:
        """Max function that works in python 3."""
        return max((x for x in lst if x is not None), default=None)

    def _max_timestamps(
        self, path: Path, remove: bool, compare_tstamp: Optional[float]
    ) -> Optional[float]:
        """Compare a timestamp file to one passed in. Get the max."""
        tstamp = self._get_timestamp_cached(path, remove)
        return self.max_none((tstamp, compare_tstamp))

    def _get_parent_timestamp(
        self, path: Path, mtime: Optional[float]
    ) -> Optional[float]:
        """
        Get the timestamps up the directory tree. All the way to root.

        Because they affect every subdirectory.
        """
        # max between the parent timestamp the one passed in
        mtime = self._max_timestamps(path, False, mtime)

        if path != path.parent:
            # recurse up if we're not at the root
            mtime = self._get_parent_timestamp(path.parent, mtime)

        return mtime

    def get_walk_after(
        self, path: Path, optimize_after: Optional[float] = None
    ) -> Optional[float]:
        """
        Figure out the which mtime to check against.

        If we have to look up the path return that.
        """
        if self._settings.optimize_after is not None:
            return self._settings.optimize_after

        if path.is_file():
            path = path.parent

        if optimize_after is None:
            optimize_after = self._get_parent_timestamp(path, None)
        after = self._max_timestamps(path, True, optimize_after)
        return after

    def _should_record_timestamp(self, path: Path) -> Tuple[bool, str]:
        """Determine if we should we record a timestamp at all."""
        record = True
        reason = _REASON_DEFAULT
        if (
            self._settings.test
            or self._settings.list_only
            or not self._settings.record_timestamp
        ):
            record = False
        elif not self._settings.follow_symlinks and path.is_symlink():
            record = False
            reason = _REASON_SYMLINK
        elif not path.exists() or not path.is_dir():
            record = False
            reason = _REASON_NONDIR

        return record, reason

    def _record_timestamp(self, full_path: Path) -> Optional[Path]:
        """Record the timestamp utilitiy without extra actios."""
        record_filepath = full_path / RECORD_FILENAME
        try:
            record_filepath.touch()
            if self._settings.verbose:
                print(f"Set timestamp: {record_filepath}")
        except OSError as err:
            print(f"Could not set timestamp in {full_path}: {err.strerror}")
            return None
        return record_filepath

    def record_timestamp(self, full_path: Path) -> None:
        """Record the timestamp of running in a dotfile."""
        record, reason = self._should_record_timestamp(full_path)
        if not record:
            if self._settings.verbose:
                print(reason)
            return

        record_filepath = self._record_timestamp(full_path)
        if record_filepath is None:
            return

        self._remove_old_timestamps(full_path, record_filepath)
