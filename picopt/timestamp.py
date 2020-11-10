"""Timestamp writer for keeping track of bulk optimizations."""
from datetime import datetime
from pathlib import Path
from typing import Dict
from typing import Optional
from typing import Tuple

from ruamel.yaml import YAML

from picopt import PROGRAM_NAME
from picopt.settings import Settings


OLD_TIMESTAMP_FN = f".{PROGRAM_NAME}_timestamp"
TIMESTAMPS_FN = f".{PROGRAM_NAME}_timestamps.yaml"


class Timestamp(object):
    """Timestamp object to hold settings and caches."""

    yaml = YAML()

    def __init__(self, settings: Settings, dump_path: Path) -> None:
        """Initialize instance variables."""
        self._settings = settings
        self.yaml.allow_duplicate_keys = True
        if dump_path.is_file():
            dump_path = dump_path.parent
        self._dump_path = dump_path / TIMESTAMPS_FN
        self._timestamps = self._load_timestamps(dump_path)

    def _get_timestamp(self, path: Path) -> Optional[float]:
        """Get the timestamp from the cache."""
        mtime: Optional[float] = None
        while path != path.parent:
            mtime = self._timestamps.get(path)
            if mtime is not None:
                break
            path = path.parent

        return mtime

    def _max_timestamps(
        self, path: Path, compare_tstamp: Optional[float]
    ) -> Optional[float]:
        """Compare a timestamp file to one passed in. Get the max."""
        tstamp = self._get_timestamp(path)
        return self.max_none((tstamp, compare_tstamp))

    def _get_timestamp_recursive_up(
        self, path: Path, mtime: Optional[float]
    ) -> Optional[float]:
        """
        Get the timestamps up the directory tree. All the way to root.

        Because they affect every subdirectory.
        """
        # max between the parent timestamp the one passed in
        mtime = self._max_timestamps(path, mtime)

        if path != path.parent:
            # recurse up if we're not at the root
            mtime = self._get_timestamp_recursive_up(path.parent, mtime)

        return mtime

    def _should_record_timestamp(self, path: Path) -> bool:
        """Determine if we should we record a timestamp at all."""
        # TODO simplify
        record = True
        if (
            self._settings.test
            or self._settings.list_only
            or not self._settings.record_timestamp
        ):
            record = False
        elif not self._settings.follow_symlinks and path.is_symlink():
            record = False
        elif not path.exists():
            record = False

        return record

    def record_timestamp(
        self, full_path: Path, mtime: Optional[float] = None
    ) -> Optional[float]:
        """Record the timestamp."""
        if not self._should_record_timestamp(full_path):
            return None
        if mtime is None:
            mtime = datetime.now().timestamp()
        self._timestamps[full_path] = mtime
        self._dump_append(full_path, mtime)
        return mtime

    def _load_one_timestamps_file(self, timestamps_path: Path):
        if not timestamps_path.is_file():
            return None

        timestamps: Dict = {}
        yaml_timestamps: Optional[Dict] = self.yaml.load(timestamps_path)
        if not yaml_timestamps:
            return timestamps
        for path_str, timestamp in yaml_timestamps.items():
            try:
                timestamps[Path(path_str)] = float(timestamp)
            except Exception:
                print(f"Invalid timestamp for {path_str}: {timestamp}")
        return timestamps

    def _load_timestamps(self, timestamps_path: Path):
        if timestamps_path.is_dir():
            # fix path to be a file
            timestamps_path = timestamps_path / TIMESTAMPS_FN

        timestamps = self._load_one_timestamps_file(timestamps_path)

        if (
            timestamps is None
            and timestamps_path.parent != timestamps_path.parent.parent
        ):
            # Recurse up
            timestamps = self._load_timestamps(timestamps_path.parent.parent)

        if timestamps is None:
            if self._settings.verbose:
                print("No timestamp files found.")
            timestamps = {}

        return timestamps

    def _dump_append(self, path, mtime):
        with open(self._dump_path, "a") as tsf:
            tsf.write(f"{path}: {mtime}\n")

    def _serialize_timestamps(self):
        dumpable_timestamps = {}
        for path, timestamp in self._timestamps.items():
            if timestamp is not None:
                dumpable_timestamps[str(path)] = timestamp
        return dumpable_timestamps

    def dump_timestamps(self):
        """Serialize timestamps and dump to file."""
        # Could do with unsafe YAML, but this seems better
        dumpable_timestamps = self._serialize_timestamps()
        self.yaml.dump(dumpable_timestamps, self._dump_path)

    @staticmethod
    def max_none(lst: Tuple[Optional[float], Optional[float]]) -> Optional[float]:
        """Max function that works in python 3."""
        return max((x for x in lst if x is not None), default=None)

    def get_walk_after(
        self, path: Path, optimize_after: Optional[float] = None
    ) -> Optional[float]:
        """
        Figure out the which mtime to check against.

        Passes in optimize_after from above to compare against
        If we have to look up the path return that.
        """
        if self._settings.optimize_after is not None:
            return self._settings.optimize_after

        optimize_after = self._get_timestamp_recursive_up(path, None)
        after = self._max_timestamps(path, optimize_after)
        return after

    def upgrade_old_timestamp(self, old_timestamp_path: Path) -> Optional[float]:
        """Get the timestamp from a old style timestamp file."""
        if self._settings.verbose > 2:
            print("looking for", old_timestamp_path)
        if not old_timestamp_path.exists():
            return None

        mtime = old_timestamp_path.stat().st_mtime
        mtime_str = datetime.fromtimestamp(mtime)
        path = old_timestamp_path.parent
        print(f"Found old style timestamp {path}:{mtime_str}")
        self.record_timestamp(path, mtime)
        try:
            old_timestamp_path.unlink()
        except OSError:
            print(f"Could not remove old timestamp: {old_timestamp_path}")
        return mtime

    def upgrade_old_parent_timestamps(self, path: Path) -> Optional[float]:
        """Walk up to the root eating old style timestamps."""
        old_timestamp_path = path / OLD_TIMESTAMP_FN
        path_mtime = self.upgrade_old_timestamp(old_timestamp_path)
        if path.parent != path:
            parent_mtime = self.upgrade_old_parent_timestamps(path.parent)
            path_mtime = self.max_none((parent_mtime, path_mtime))
        return path_mtime

    def compact_timestamps(self, root_path: Path) -> None:
        """Compact the timestamp cache and dump it."""
        max_timestamp = None
        delete_keys = set()
        for path in self._timestamps.keys():
            if root_path in path.parents:
                timestamp = self._timestamps.get(path)
                delete_keys.add(path)
                max_timestamp = self.max_none((timestamp, max_timestamp))
        for path in delete_keys:
            del self._timestamps[path]
        self._timestamps[root_path] = max_timestamp
        self.dump_timestamps()

    def consume_child_timestamps(self, timestamps_path: Path) -> None:
        """Consume a child timestamp and add its values to our root."""
        timestamps = self._load_one_timestamps_file(timestamps_path)
        # If the timestamp in the new batch is a child of an existing
        #   timestamp and is earlier ignore it. Otherwise add it.
        for path, timestamp in timestamps.items():
            # TODO: could probably simplify this logic
            ignore = True
            for root_path in set(self._timestamps.keys()):
                if root_path == path or root_path in path.parents:
                    root_timestamp = self._timestamps[root_path]
                    if timestamp > root_timestamp:
                        ignore = False
                        break
            if not ignore:
                self._timestamps[path] = timestamp
        self.dump_timestamps()  # TODO could interfere with appending
        timestamps_path.unlink()
