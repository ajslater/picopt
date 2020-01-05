"""Timestamp writer for keeping track of bulk optimizations."""
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

from . import PROGRAM_NAME
from .settings import Settings

RECORD_FILENAME = f'.{PROGRAM_NAME}_timestamp'
TIMESTAMP_CACHE: Dict[Path, Optional[float]] = {}
OLD_TIMESTAMPS: Set[Path] = set()


def _get_timestamp(dirname_full: Path,
                   remove: bool) -> Optional[float]:
    """
    Get the timestamp from the timestamp file.

    Optionally mark it for removal if we're going to write another one.
    """
    record_path = Path(dirname_full).joinpath(RECORD_FILENAME)

    if not record_path.exists():
        return None

    mtime = record_path.stat().st_mtime
    mtime_str = datetime.fromtimestamp(mtime)
    print(f'Found timestamp {dirname_full}:{mtime_str}')
    if Settings.record_timestamp and remove:
        OLD_TIMESTAMPS.add(record_path)
    return mtime


def _get_timestamp_cached(dirname_full: Path,
                          remove: bool) -> Optional[float]:
    """
    Get the timestamp from the cache or fill the cache.

    Much quicker than reading the same files over and over
    """
    if dirname_full not in TIMESTAMP_CACHE:
        mtime = _get_timestamp(dirname_full, remove)
        TIMESTAMP_CACHE[dirname_full] = mtime
    return TIMESTAMP_CACHE[dirname_full]


def max_none(lst: Tuple[Optional[float],
                        Optional[float]]) -> Optional[float]:
    """Max function that works in python 3."""
    return max((x for x in lst if x is not None), default=None)


def _max_timestamps(dirname_full: Path, remove: bool,
                    compare_tstamp: Optional[float]) -> Optional[float]:
    """Compare a timestamp file to one passed in. Get the max."""
    tstamp = _get_timestamp_cached(dirname_full, remove)
    return max_none((tstamp, compare_tstamp))


def _get_parent_timestamp(path: Path,
                          mtime: Optional[float]) -> Optional[float]:
    """
    Get the timestamps up the directory tree. All the way to root.

    Because they affect every subdirectory.
    """
    parent_path = path.parent

    # max between the parent timestamp the one passed in
    mtime = _max_timestamps(parent_path, False, mtime)

    if path != parent_path.parent:
        # this is only called if we're not at the root
        mtime = _get_parent_timestamp(parent_path, mtime)

    return mtime


def get_walk_after(filename: Path,
                   optimize_after: Optional[float] = None) \
                        -> Optional[float]: # noqa
    """
    Figure out the which mtime to check against.

    If we have to look up the path return that.
    """
    if Settings.optimize_after is not None:
        return Settings.optimize_after

    dirname = Path(filename).parent
    if optimize_after is None:
        optimize_after = _get_parent_timestamp(dirname, optimize_after)
    return _max_timestamps(dirname, True, optimize_after)


def record_timestamp(full_path: Path) -> None:
    """Record the timestamp of running in a dotfile."""
    if Settings.test or Settings.list_only or not Settings.record_timestamp:
        return
    if not Settings.follow_symlinks and full_path.is_symlink():
        if Settings.verbose:
            print('Not setting timestamp because not following symlinks')
        return
    if not full_path.is_dir():
        if Settings.verbose:
            print('Not setting timestamp for a non-directory')
        return

    record_filepath = full_path.joinpath(RECORD_FILENAME)
    try:
        record_filepath.touch()
        if Settings.verbose:
            print(f"Set timestamp: {record_filepath}")
        for path in OLD_TIMESTAMPS:
            if str(path).startswith(str(full_path)) and \
               not path.samefile(record_filepath):
                # only remove timestamps below the curent path
                # but don't remove the timestamp we just set!
                path.unlink()
                if Settings.verbose:
                    print(f'Removed old timestamp: {path}')
    except IOError:
        print(f"Could not set timestamp in {full_path}")
