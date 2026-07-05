"""Per-directory completion tracking for compacted timestamp writes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from treestamps import Grovestamps


@dataclass
class _DirTracker:
    """Track pending children of a walked directory for timestamp writes."""

    top_path: Path
    pending: int = 0
    sealed: bool = False
    # A child errored: writing a compacted dir timestamp would cover the
    # failed file and permanently skip it on subsequent runs.
    errored: bool = False


class DirTimestamper:
    """
    Write compacted directory timestamps once a directory fully completes.

    The walk layer announces directories (``begin_dir`` … ``seal_dir``) and
    the scheduler reports each top-level child's completion; when a sealed
    directory has no pending children and none errored, its timestamp is
    written with compaction and completion cascades to the parent tracker.
    """

    def __init__(self, timestamps: Grovestamps | None) -> None:
        """Store the timestamps sink."""
        self._timestamps = timestamps
        self._trackers: dict[Path, _DirTracker] = {}

    def begin_dir(self, top_path: Path, dir_path: Path) -> None:
        """Register a directory whose children are about to be enqueued."""
        parent_tracker = self._trackers.get(dir_path.parent)
        if parent_tracker is not None:
            parent_tracker.pending += 1
        self._trackers[dir_path] = _DirTracker(top_path=top_path)

    def seal_dir(self, dir_path: Path) -> None:
        """Mark a directory as fully enumerated; finalize if nothing pends."""
        tracker = self._trackers.get(dir_path)
        if tracker is None:
            return
        tracker.sealed = True
        if tracker.pending <= 0:
            self._finalize(dir_path, tracker)

    def cancel_dir(self, dir_path: Path) -> None:
        """Remove a directory tracker without finalizing (walk errors)."""
        tracker = self._trackers.pop(dir_path, None)
        if tracker is None:
            return
        parent_dir = dir_path.parent
        if parent_dir in self._trackers:
            self.child_done(parent_dir)

    def enqueue_child(self, child_path: Path) -> None:
        """Increment a directory's pending count for a newly enqueued child."""
        tracker = self._trackers.get(child_path.parent)
        if tracker is not None:
            tracker.pending += 1

    def mark_errored(self, dir_path: Path) -> None:
        """Poison a directory's timestamp write after a child error."""
        tracker = self._trackers.get(dir_path)
        if tracker is not None:
            tracker.errored = True

    def child_done(self, parent_dir: Path, *, errored: bool = False) -> None:
        """Decrement a directory's pending count; finalize when ready."""
        tracker = self._trackers.get(parent_dir)
        if tracker is None:
            return
        if errored:
            tracker.errored = True
        tracker.pending -= 1
        if tracker.pending <= 0 and tracker.sealed:
            self._finalize(parent_dir, tracker)

    def __contains__(self, dir_path: Path) -> bool:
        """Whether a directory is currently tracked."""
        return dir_path in self._trackers

    def _finalize(self, dir_path: Path, tracker: _DirTracker) -> None:
        """Write directory timestamp with compaction and cascade to parent."""
        del self._trackers[dir_path]
        # An errored child means this directory is not fully optimized; a
        # compacted dir stamp would cover the failed file and skip it on
        # every future run. Per-file stamps for the successes remain.
        if self._timestamps and not tracker.errored:
            self._timestamps.set(tracker.top_path, dir_path, compact=True)
        parent_dir = dir_path.parent
        if parent_dir in self._trackers:
            self.child_done(parent_dir, errored=tracker.errored)
