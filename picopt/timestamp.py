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
# TODO These should not be module global
TIMESTAMP_CACHE: Dict[Path, Optional[float]] = {}
OLD_TIMESTAMPS: Set[Path] = set()


def _get_timestamp(
    settings: Settings, dirname_full: Path, remove: bool
) -> Optional[float]:
    """
    Get the timestamp from the timestamp file.

    Optionally mark it for removal if we're going to write another one.
    """
    record_path = dirname_full / RECORD_FILENAME

    if not record_path.exists():
        return None

    mtime = record_path.stat().st_mtime
    mtime_str = datetime.fromtimestamp(mtime)
    print(f"Found timestamp {dirname_full}:{mtime_str}")
    if settings.record_timestamp and remove:
        OLD_TIMESTAMPS.add(record_path)
    return mtime


def _get_timestamp_cached(
    settings: Settings, dirname_full: Path, remove: bool
) -> Optional[float]:
    """
    Get the timestamp from the cache or fill the cache.

    Much quicker than reading the same files over and over
    """
    if dirname_full not in TIMESTAMP_CACHE:
        mtime = _get_timestamp(settings, dirname_full, remove)
        TIMESTAMP_CACHE[dirname_full] = mtime
    return TIMESTAMP_CACHE[dirname_full]


def max_none(lst: Tuple[Optional[float], Optional[float]]) -> Optional[float]:
    """Max function that works in python 3."""
    return max((x for x in lst if x is not None), default=None)


def _max_timestamps(
    settings: Settings,
    dirname_full: Path,
    remove: bool,
    compare_tstamp: Optional[float],
) -> Optional[float]:
    """Compare a timestamp file to one passed in. Get the max."""
    tstamp = _get_timestamp_cached(settings, dirname_full, remove)
    return max_none((tstamp, compare_tstamp))


def _get_parent_timestamp(
    settings: Settings, path: Path, mtime: Optional[float]
) -> Optional[float]:
    """
    Get the timestamps up the directory tree. All the way to root.

    Because they affect every subdirectory.
    """
    parent_path = path.parent

    # max between the parent timestamp the one passed in
    mtime = _max_timestamps(settings, parent_path, False, mtime)

    if path != parent_path.parent:
        # this is only called if we're not at the root
        mtime = _get_parent_timestamp(settings, parent_path, mtime)

    return mtime


def get_walk_after(
    settings: Settings, filename: Path, optimize_after: Optional[float] = None
) -> Optional[float]:
    """
    Figure out the which mtime to check against.

    If we have to look up the path return that.
    """
    if settings.optimize_after is not None:
        return settings.optimize_after

    dirname = Path(filename).parent
    if optimize_after is None:
        optimize_after = _get_parent_timestamp(settings, dirname, optimize_after)
    return _max_timestamps(settings, dirname, True, optimize_after)


def _should_record_timestamp(settings: Settings, full_path: Path) -> Tuple[bool, str]:
    """Determine if we should we record a timestamp at all."""
    record = True
    reason = _REASON_DEFAULT
    if settings.test or settings.list_only or not settings.record_timestamp:
        record = False
    elif not settings.follow_symlinks and full_path.is_symlink():
        record = False
        reason = _REASON_SYMLINK
    elif not full_path.is_dir():
        record = False
        reason = _REASON_NONDIR
    return record, reason


def _remove_old_timestamps(
    settings: Settings, full_path: Path, record_filepath: Path
) -> Dict[Path, Optional[OSError]]:
    """Remove old timestamps after setting a new one."""
    removed: Dict[Path, Optional[OSError]] = {}
    for path in OLD_TIMESTAMPS:
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

    if not settings.verbose:
        return removed

    for path, error in removed.items():
        if error is None:
            print(f"Removed old timestamp: {path}")
        else:
            print(f"Could not remove old timestamp: {path}: {error.strerror}")

    return removed


def _record_timestamp(settings: Settings, full_path: Path) -> Optional[Path]:
    """Record the timestamp utilitiy without extra actios."""
    record_filepath = full_path / RECORD_FILENAME
    try:
        record_filepath.touch()
        if settings.verbose:
            print(f"Set timestamp: {record_filepath}")
    except OSError as err:
        print(f"Could not set timestamp in {full_path}: {err.strerror}")
        return None
    return record_filepath


def record_timestamp(settings: Settings, full_path: Path) -> None:
    """Record the timestamp of running in a dotfile."""
    record, reason = _should_record_timestamp(settings, full_path)
    if not record:
        if settings.verbose:
            print(reason)
        return

    record_filepath = _record_timestamp(settings, full_path)
    print("filepath", record_filepath)
    if record_filepath is None:
        return

    _remove_old_timestamps(settings, full_path, record_filepath)
