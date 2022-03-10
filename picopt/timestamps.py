"""Timestamp writer for keeping track of bulk optimizations."""
import os

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from ruamel.yaml import YAML


class Timestamps:
    """Timestamp object to hold settings and caches."""

    @staticmethod
    def dirpath(path: Path):
        return path if path.is_dir() else path.parent

    @staticmethod
    def max_none(a: Optional[float], b: Optional[float]) -> Optional[float]:
        """Max function that works in python 3."""
        return max((x for x in (a, b) if x is not None), default=None)

    def _load_one_timestamps_file(self, timestamps_path: Path) -> Optional[Dict]:
        """Load timestamps from a file."""
        if not timestamps_path.is_file():
            return None

        timestamps: Dict = {}
        try:
            yaml_timestamps: Optional[Dict] = self._YAML.load(timestamps_path)
            if not yaml_timestamps:
                return timestamps
            for path_str, ts_str in yaml_timestamps.items():
                try:
                    path = Path(path_str)
                    ts = float(ts_str)
                    if not path.is_absolute():
                        # Load relative path. Normal
                        timestamps[path] = ts
                    elif path.is_relative_to(self._dump_path):
                        # Convert absolute path to relative.
                        relative_path = path.relative_to(self._dump_path.parent)
                        timestamps[relative_path] = ts
                    elif self._dump_path.is_relative_to(path):
                        # Convert parent path to local path.
                        timestamps[self._dump_path.parent] = self.max_none(
                            ts, self._timestamps.get(self._dump_path.parent)
                        )
                except Exception as exc:
                    print(f"Invalid timestamp for {path_str}: {ts_str} {exc}")
        except Exception as exc:
            print(f"Error parsing timestamp file: {timestamps_path}")
            print(exc)
        return timestamps

    def _load_timestamps(self, timestamps_path: Path):
        timestamps_path = timestamps_path / self.filename
        timestamps = self._load_one_timestamps_file(timestamps_path)

        if (
            timestamps is None
            and timestamps_path.parent != timestamps_path.parent.parent
        ):
            # if no file found and not at root recurse up.
            timestamps = self._load_timestamps(timestamps_path.parent.parent)

        if timestamps is None:
            if self._verbose:
                print("No timestamp files found.")
            timestamps = {}

        return timestamps

    def _consume_child_timestamps(self, timestamps_path: Path) -> None:
        """Consume a child timestamp and add its values to our root."""
        child_timestamps = self._load_one_timestamps_file(timestamps_path)
        if child_timestamps is not None:
            for child_path, child_timestamp in child_timestamps.items():
                timestamp = self.get(child_path)
                if timestamp is None or child_timestamp > timestamp:
                    self.set(child_path, child_timestamp)
        timestamps_path.unlink()
        if self._verbose:
            print(f"Consumed child timestamp: {timestamps_path}")

    def _consume_all_child_timestamps(self, path: Path):
        for root, dirnames, filenames in os.walk(path):
            root_path = Path(root)
            if self.filename in filenames:
                self._consume_child_timestamps(root_path / self.filename)
            for dirname in dirnames:
                self._consume_all_child_timestamps(Path(dirname))

    def _compact_timestamps_below(self, root_path: Path) -> None:
        """Compact the timestamp cache below a particular path."""
        if not root_path.is_dir():
            return
        root_timestamp = self._timestamps.get(root_path)
        delete_keys = set()
        for path, timestamp in self._timestamps.items():
            if (
                path.is_relative_to(root_path) and timestamp < root_timestamp
            ) or timestamp is None:
                delete_keys.add(path)
        for path in delete_keys:
            del self._timestamps[path]
        if self._verbose > 1:
            print(f"Compacted timestamps: {root_path}: {root_timestamp}")

    def _serialize_timestamps(self):
        """Dumpable timestamp paths need to be strings."""
        dumpable_timestamps = {}
        for path, timestamp in self._timestamps.items():
            dumpable_timestamps[str(path)] = timestamp
        return dumpable_timestamps

    def __init__(self, program_name: str, dump_path: Path, verbose: int = 0) -> None:
        """Initialize instance variables."""
        if not dump_path.is_dir():
            raise ValueError("dump_path must be a directory")
        self._verbose = verbose
        self._YAML = YAML()
        self._YAML.allow_duplicate_keys = True
        self.filename = f".{program_name}_timestamps.yaml"
        self._dump_path = dump_path / self.filename
        self._timestamps = self._load_timestamps(dump_path)
        self._consume_all_child_timestamps(dump_path)

    def get(self, path: Path) -> Optional[float]:
        """
        Get the timestamps up the directory tree. All the way to root.

        Because they affect every subdirectory.
        """
        if path.is_absolute():
            path = path.relative_to(self._dump_path.parent)
        mtime: Optional[float] = None
        while path != path.parent:
            mtime = self.max_none(mtime, self._timestamps.get(path))
            path = path.parent

        return mtime

    def set(
        self, full_path: Path, mtime: Optional[float] = None, compact: bool = False
    ) -> Optional[float]:
        """Record the timestamp."""
        if mtime is None:
            mtime = datetime.now().timestamp()
        relative_path = full_path.relative_to(self._dump_path.parent)
        self._timestamps[relative_path] = mtime
        if compact:
            self._compact_timestamps_below(relative_path)
        with self._dump_path.open("a") as tsf:
            tsf.write(f"{full_path}: {mtime}\n")
        return mtime

    def dump_timestamps(self) -> None:
        """Serialize timestamps and dump to file."""
        dumpable_timestamps = self._serialize_timestamps()
        self._YAML.dump(dumpable_timestamps, self._dump_path)
