"""Upgrade old picopt timestamps to new ones."""
import os

from datetime import datetime
from pathlib import Path
from typing import Optional

from picopt import PROGRAM_NAME
from picopt.timestamps import Timestamps


_OLD_TIMESTAMPS_NAME = f".{PROGRAM_NAME}_timestamp"


def _upgrade_old_timestamp(
    timestamps: Timestamps, old_timestamp_path: Path
) -> Optional[float]:
    """Get the timestamp from a old style timestamp file."""
    if not old_timestamp_path.exists():
        return None

    mtime = old_timestamp_path.stat().st_mtime
    mtime_str = datetime.fromtimestamp(mtime)
    path = old_timestamp_path.parent
    timestamps.set(path, mtime)
    try:
        old_timestamp_path.unlink()
        print(f"Upgraded old style timestamp {path}:{mtime_str}")
    except OSError:
        print(f"Could not remove old timestamp: {old_timestamp_path}")

    return mtime


def _upgrade_old_parent_timestamps(
    timestamps: Timestamps, path: Path
) -> Optional[float]:
    """Walk up to the root eating old style timestamps."""
    old_timestamp_path = path / _OLD_TIMESTAMPS_NAME
    path_mtime = _upgrade_old_timestamp(timestamps, old_timestamp_path)
    if path.parent != path:
        parent_mtime = _upgrade_old_parent_timestamps(timestamps, path.parent)
        path_mtime = Timestamps.max_none(parent_mtime, path_mtime)
    return path_mtime


def _upgrade_old_child_timestamps(timestamps: Timestamps, top_path: Path):
    for root, dirnames, filenames in os.walk(top_path):
        root_path = Path(root)
        if _OLD_TIMESTAMPS_NAME in filenames:
            _upgrade_old_timestamp(timestamps, root_path / _OLD_TIMESTAMPS_NAME)
        for dirname in dirnames:
            _upgrade_old_child_timestamps(timestamps, root_path / dirname)


def migrate_timestamps(timestamps: Timestamps, top_path: Path):
    """Hold the new timestamp object and upgrade all parents."""
    _upgrade_old_parent_timestamps(timestamps, top_path)
    _upgrade_old_child_timestamps(timestamps, top_path)
