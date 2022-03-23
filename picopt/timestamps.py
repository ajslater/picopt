"""Timestamp writer for keeping track of bulk optimizations."""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Set, TextIO

from ruamel.yaml import YAML


class Timestamps:
    """Timestamp object to hold settings and caches."""

    _CONFIG_TAG = "config"
    _WAL_TAG = "wal"

    @staticmethod
    def max_none(a: Optional[float], b: Optional[float]) -> Optional[float]:
        """Max function that works in python 3."""
        return max((x for x in (a, b) if x is not None), default=None)

    @staticmethod
    def get_timestamps_filename(program_name: str) -> str:
        """Return the timestamps filename for a program."""
        return f".{program_name}_timestamps.yaml"

    @staticmethod
    def get_wal_filename(program_name: str) -> str:
        """Return the write ahead log filename for the program."""
        return f".{program_name}_timestamps.wal.yaml"

    @classmethod
    def _normalize_config(cls, config: Optional[Dict]) -> Optional[Dict]:
        if config is None:
            return None
        new_config: Dict = {}
        for key, value in config.items():
            if isinstance(value, (list, tuple, set)):
                original_type = type(value)
                new_config[key] = original_type(sorted(set(value)))
            elif isinstance(value, dict):
                new_config[key] = cls._normalize_config(value)
            else:
                new_config[key] = value

        return new_config

    def _to_absolute_path(self, root: Path, path: Path) -> Optional[Path]:
        """Convert paths to relevant absolute paths."""
        if path.is_absolute():
            full_path = path
        else:
            full_path = root / path

        if not full_path.is_relative_to(self.dir):
            if self.dir.is_relative_to(full_path):
                full_path = self.dir
            else:
                if self._verbose:
                    print(f"Timestamp {full_path} is not related to {self.dir}.")
        return full_path

    def _load_timestamp_entry(self, root: Path, path_str: str, ts: float) -> None:
        try:
            full_path = self._to_absolute_path(root, Path(path_str))
            if full_path is None:
                if self._verbose > 2:
                    print(f"Irrelevant timestamp ignored: {path_str}: {ts}")
                return

            old_ts = self.get(full_path)
            if full_path not in self._timestamps or old_ts is None or ts > old_ts:
                self._timestamps[full_path] = ts
        except Exception as exc:
            print(f"Invalid timestamp for {path_str}: {ts} {exc}")

    def _load_timestamps_file(self, timestamps_path: Path) -> None:
        """Load timestamps from a file."""
        if not timestamps_path.is_file():
            return None

        try:
            yaml = self._YAML.load(timestamps_path)
            if not yaml:
                return

            # Config
            try:
                yaml_config = yaml.pop(self._CONFIG_TAG)
                yaml_config = self._normalize_config(yaml_config)
            except KeyError:
                yaml_config = None
            if self._config != yaml_config:
                # Only load timestamps for comparable configs
                return

            # WAL
            try:
                wal = yaml.pop(self._WAL_TAG)
            except KeyError:
                wal = []

            # Timestamps
            entries = list(yaml.items())

            # Wal entries afterwards
            for entry in wal:
                for path_str, ts in entry.items():
                    entries += [(path_str, ts)]

            for path_str, ts in entries:
                self._load_timestamp_entry(timestamps_path.parent, path_str, ts)
        except Exception as exc:
            print(f"Error parsing timestamps file: {timestamps_path}")
            print(exc)

    def _consume_child_timestamps(self, path: Path) -> None:
        """Consume a child timestamp and add its values to our root."""
        if not path.is_file():
            return
        self._load_timestamps_file(path)
        self._consumed_paths.add(path)
        if self._verbose:
            print(f"Read timestamps from {path}")

    def _consume_all_child_timestamps(self, path: Path) -> None:
        # TODO probably replace with os.walk
        # This probably doesn't have full paths
        if not path.is_dir():
            return
        self._consume_child_timestamps(path / self.filename)
        self._consume_child_timestamps(path / self.wal_filename)
        for dir_entry in path.iterdir():
            self._consume_all_child_timestamps(dir_entry)

    def _load_parent_timestamps(self, path: Path) -> None:
        if path.parent == path.parent.parent:
            return
        parent = path.parent
        self._load_timestamps_file(parent / self.filename)
        self._load_timestamps_file(parent / self.wal_filename)
        self._load_parent_timestamps(parent)

    def _compact_timestamps_below(self, root_path: Path, root_timestamp: float) -> None:
        """Compact the timestamp cache below a particular path."""
        full_root_path = self.dir / root_path
        if not full_root_path.is_dir():
            return
        delete_keys = set()
        for path, timestamp in self._timestamps.items():
            full_path = self.dir / path
            if (
                full_path.is_relative_to(full_root_path) and timestamp < root_timestamp
            ) or timestamp is None:
                delete_keys.add(full_path)
        for del_path in delete_keys:
            del self._timestamps[del_path]
        if self._verbose > 1:
            print(f"Compacted timestamps: {full_root_path}: {root_timestamp}")

    def _get_relative_path_str(self, full_path: Path) -> str:
        return str(full_path.relative_to(self.dir))

    def _serialize_timestamps(self):
        """Dumpable timestamp paths need to be strings."""
        dumpable_timestamps = {}
        for full_path, timestamp in self._timestamps.items():
            path_str = self._get_relative_path_str(full_path)
            dumpable_timestamps[path_str] = timestamp
        return dumpable_timestamps

    def _set_dumpable_config(self, yaml: dict) -> None:
        if self._config is not None:
            yaml[self._CONFIG_TAG] = dict(sorted(self._config.items()))

    def __init__(
        self,
        program_name: str,
        dir: Path,
        verbose: int = 0,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize instance variables."""
        if not dir.is_dir():
            raise ValueError("'dir' argument must be a directory")
        self.dir = dir
        self._verbose = verbose
        self._YAML = YAML()
        self._YAML.allow_duplicate_keys = True
        self.filename = self.get_timestamps_filename(program_name)
        self.wal_filename = self.get_wal_filename(program_name)
        self._dump_path = self.dir / self.filename
        self._wal_path = self.dir / self.wal_filename
        self._wal: Optional[TextIO] = None
        self._consumed_paths: Set[Path] = set()
        self._config: Optional[Dict] = self._normalize_config(config)
        self._timestamps: Dict[Path, float] = {}
        self._consume_all_child_timestamps(self.dir)
        self._load_parent_timestamps(self.dir)

    def get(self, path: Path) -> Optional[float]:
        """
        Get the timestamps up the directory tree. All the way to root.

        Because they affect every subdirectory.
        """
        mtime: Optional[float] = None
        full_path = self._to_absolute_path(self.dir, path)
        if full_path is None:
            return mtime
        while full_path != full_path.parent:
            mtime = self.max_none(mtime, self._timestamps.get(full_path))
            full_path = full_path.parent
        mtime = self.max_none(mtime, self._timestamps.get(full_path))

        return mtime

    def _close_wal(self) -> None:
        if self._wal is None:
            return
        try:
            self._wal.close()
        except AttributeError:
            pass
        self._wal = None

    def _init_wal(self) -> None:
        yaml: Dict = {}
        self._set_dumpable_config(yaml)
        self._close_wal()
        self._YAML.dump(yaml, self._wal_path)
        self._consumed_paths.add(self._wal_path)
        self._wal = self._wal_path.open("a")
        self._wal.write(self._WAL_TAG + ":\n")

    def set(
        self, path: Path, mtime: Optional[float] = None, compact: bool = False
    ) -> Optional[float]:
        """Record the timestamp."""
        # Get params
        full_path = self._to_absolute_path(self.dir, path)
        if full_path is None:
            if self._verbose:
                print(f"Timestamp {full_path} is not related to {self.dir}.")
            return None
        if mtime is None:
            mtime = datetime.now().timestamp()

        old_mtime = self._timestamps.get(full_path)
        if old_mtime is not None and old_mtime > mtime:
            return None

        self._timestamps[full_path] = mtime
        if compact and full_path.is_dir():
            self._compact_timestamps_below(full_path, mtime)
        if not self._wal:
            self._init_wal()
        if self._wal:
            path_str = self._get_relative_path_str(full_path)
            self._wal.write(f"- {path_str}: {mtime}\n")
        return mtime

    def dump_timestamps(self) -> None:
        """Serialize timestamps and dump to file."""
        yaml: Dict = {}
        self._set_dumpable_config(yaml)
        dumpable_timestamps = self._serialize_timestamps()
        yaml.update(dumpable_timestamps)

        self._YAML.dump(yaml, self._dump_path)
        self._close_wal()
        if self._consumed_paths:
            for path in self._consumed_paths:
                path.unlink(missing_ok=True)
            self._consumed_paths = set()
