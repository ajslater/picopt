"""Timestamp writer for keeping track of bulk optimizations."""
import time

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from dateutil.parser import parse
from ruamel.yaml import YAML


class Timestamp:
    """Timestamp object to hold settings and caches."""

    _YAML = YAML()

    def __init__(self, program_name: str, dump_path: Path, verbose: int = 0) -> None:
        """Initialize instance variables."""
        self._verbose = verbose
        self._YAML.allow_duplicate_keys = True
        if dump_path.is_file():
            dump_path = dump_path.parent
        self.old_timestamp_name = f".{program_name}_timestamp"
        self.timestamps_name = f".{program_name}_timestamps.yaml"
        self._dump_path = dump_path / self.timestamps_name
        self._timestamps = self._load_timestamps(dump_path)

    @staticmethod
    def parse_date_string(date_str: str) -> float:
        """Turn a datetime string into an epoch float."""
        after_dt = parse(date_str)
        return time.mktime(after_dt.timetuple())

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

    def get_timestamp_recursive_up(
        self, path: Path, mtime: Optional[float] = None
    ) -> Optional[float]:
        """
        Get the timestamps up the directory tree. All the way to root.

        Because they affect every subdirectory.
        """
        # max between the parent timestamp the one passed in
        mtime = self._max_timestamps(path, mtime)

        if path != path.parent:
            # recurse up if we're not at the root
            mtime = self.get_timestamp_recursive_up(path.parent, mtime)

        return mtime

    def record_timestamp(
        self, full_path: Path, mtime: Optional[float] = None
    ) -> Optional[float]:
        """Record the timestamp."""
        if mtime is None:
            mtime = datetime.now().timestamp()
        self._timestamps[full_path] = mtime
        self._dump_append(full_path, mtime)
        return mtime

    def _load_one_timestamps_file(self, timestamps_path: Path) -> Optional[Dict]:
        if not timestamps_path.is_file():
            return None

        timestamps: Dict = {}
        try:
            yaml_timestamps: Optional[Dict] = self._YAML.load(timestamps_path)
            if not yaml_timestamps:
                return timestamps
            for path_str, timestamp in yaml_timestamps.items():
                try:
                    timestamps[Path(path_str)] = float(timestamp)
                except Exception:
                    print(f"Invalid timestamp for {path_str}: {timestamp}")
        except Exception as exc:
            print(f"Error parsing timestamp file: {timestamps_path}")
            print(exc)
        return timestamps

    def _load_timestamps(self, timestamps_path: Path):
        if timestamps_path.is_dir():
            # fix path to be a file
            timestamps_path = timestamps_path / self.timestamps_name

        timestamps = self._load_one_timestamps_file(timestamps_path)

        if (
            timestamps is None
            and timestamps_path.parent != timestamps_path.parent.parent
        ):
            # Recurse up
            timestamps = self._load_timestamps(timestamps_path.parent.parent)

        if timestamps is None:
            if self._verbose:
                print("No timestamp files found.")
            timestamps = {}

        return timestamps

    def _dump_append(self, path: Path, mtime: float) -> None:
        with open(self._dump_path, "a") as tsf:
            tsf.write(f"{path}: {mtime}\n")

    def _serialize_timestamps(self):
        dumpable_timestamps = {}
        for path, timestamp in self._timestamps.items():
            if timestamp is not None:
                dumpable_timestamps[str(path)] = timestamp
        return dumpable_timestamps

    def dump_timestamps(self) -> None:
        """Serialize timestamps and dump to file."""
        # Could do with unsafe YAML, but this seems better
        dumpable_timestamps = self._serialize_timestamps()
        self._YAML.dump(dumpable_timestamps, self._dump_path)

    @staticmethod
    def max_none(lst: Tuple[Optional[float], Optional[float]]) -> Optional[float]:
        """Max function that works in python 3."""
        return max((x for x in lst if x is not None), default=None)

    def upgrade_old_timestamp(self, old_timestamp_path: Path) -> Optional[float]:
        """Get the timestamp from a old style timestamp file."""
        if not old_timestamp_path.exists():
            return None

        mtime = old_timestamp_path.stat().st_mtime
        mtime_str = datetime.fromtimestamp(mtime)
        path = old_timestamp_path.parent
        self.record_timestamp(path, mtime)
        try:
            old_timestamp_path.unlink()
            if self._verbose:
                print(f"Upgraded old style timestamp {path}:{mtime_str}")
        except OSError:
            print(f"Could not remove old timestamp: {old_timestamp_path}")

        return mtime

    def upgrade_old_parent_timestamps(self, path: Path) -> Optional[float]:
        """Walk up to the root eating old style timestamps."""
        old_timestamp_path = path / self.old_timestamp_name
        path_mtime = self.upgrade_old_timestamp(old_timestamp_path)
        if path.parent != path:
            parent_mtime = self.upgrade_old_parent_timestamps(path.parent)
            path_mtime = self.max_none((parent_mtime, path_mtime))
        return path_mtime

    def compact_timestamps(self, root_path: Path) -> None:
        """Compact the timestamp cache and dump it."""
        max_timestamp = self._timestamps.get(root_path)
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
        if self._verbose > 1:
            print(f"Compacted timestamps: {root_path}: {max_timestamp}")

    def consume_child_timestamps(self, timestamps_path: Path) -> None:
        """Consume a child timestamp and add its values to our root."""
        timestamps = self._load_one_timestamps_file(timestamps_path)
        # If the timestamp in the new batch is a child of an existing
        #   timestamp and is earlier ignore it. Otherwise add it.
        if timestamps is not None:
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
        if self._verbose:
            print(f"Consumed child timestamp: {timestamps_path}")
