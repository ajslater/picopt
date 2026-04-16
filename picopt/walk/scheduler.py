"""
Futures-based scheduler for picopt walk/dispatch.

Replaces the old recursive main-thread _handle_container / _walk_container /
_finish_results flow with a single main-thread loop over a ProcessPoolExecutor.

Design notes (see HANDOFF-PICOPT-DISPATCH-REWRITE.md for rationale):

* One main-thread loop owns every executor.submit() call. Dispatch is not
  scattered across walk_dir / _handle_file / _handle_container anymore.
* Three job kinds: UnpackJob, OptimizeLeafJob, RepackJob. Each runs in a
  worker process, returns a plain dataclass / ReportStats, never mutates
  scheduler state directly.
* Containers become ContainerNodes that the scheduler threads together into
  a tree. Leaves are NOT nodes; they're tracked in a dict[Future, node].
* Backpressure: len(inflight) <= 2 * max_workers. Overflow sits in `ready`.
* Rollback-on-repack-failure: mark node CANCELLED, discard _optimized_contents,
  rmtree staging, and drop any late-arriving leaf results whose owning node
  has state CANCELLED.
* fail_fast: drain in-flight work, discard all CANCELLED results, rmtree every
  live node's staging dir in a finally.
* fail_fast_container: when an inner REPACK fails, cascade CANCELLED up to
  the top-level container for that subtree (but leave sibling top-paths alone).
"""

from __future__ import annotations

import shutil
import traceback
from collections import deque
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import dataclass, field
from enum import Enum, auto
from itertools import chain
from typing import TYPE_CHECKING

from picopt.report import ReportStats

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from confuse.templates import AttrDict
    from treestamps import Grovestamps

    from picopt.path import PathInfo
    from picopt.plugins.base import ContainerHandler, ImageHandler
    from picopt.printer import Printer
    from picopt.report import Totals


# --------------------------------------------------------------------- state


class NodeState(Enum):
    """Lifecycle of a ContainerNode."""

    NEW = auto()  # created, nothing submitted yet
    UNPACKING = auto()  # UnpackJob in flight
    OPTIMIZING = auto()  # children in flight
    REPACKING = auto()  # RepackJob in flight
    DONE = auto()  # repacked successfully, totals accumulated
    CANCELLED = auto()  # rollback in progress or complete; discard results


# ---------------------------------------------------------------------- jobs
#
# Job.run() is executed in a worker process. It must not touch scheduler
# state. Return values are plain data that the main thread interprets in
# _handle_completion.


@dataclass
class UnpackResult:
    """
    Return value of UnpackJob.run().

    The `handler` field is the pickle-roundtripped copy of the unpack
    handler after walk() has mutated it in the worker process. The
    scheduler MUST reassign node.handler = result.handler before doing
    anything else with the node, or subsequent reads (get_optimized_contents,
    is_do_repack, staging_dir lookup, create_repack_handler) will see the
    pre-walk() state.

    Attributes the worker's walk() may have mutated on the handler that
    matter to the main thread (grep `ContainerHandler` subclasses for the
    exact field names; they vary per concrete class):

    - staging dir path (attribute name varies: `_tmp_path`, `_unpack_dir`,
      etc. — whatever the concrete handler uses internally). The main
      thread needs this to rmtree on cleanup or rollback.
    - `comment` (bytes | None) — archive comment extracted during walk.
      `create_repack_handler` reads this and passes it to the repack
      handler constructor.
    - `_do_repack` — set True inside walk() when any child surfaces work.
      We don't rely on this because the scheduler re-derives it from
      `node.had_work` after all children complete, but concrete handlers
      may still flip it during walk() and we inherit that.
    - `_optimized_contents` (set[PathInfo]) — may have entries added for
      children that were skipped/copied verbatim (noop children). The
      scheduler appends successful leaf results to this same set, so the
      roundtrip preserves the walk()-time additions.
    - internal caches the handler populates during walk() (file lists,
      archive member tables, etc.) — opaque to the scheduler but needed
      by repack().
    """

    handler: ContainerHandler
    children: list[PathInfo]
    exc: Exception | None = None


@dataclass
class UnpackJob:
    """Run handler.walk() in a worker; return materialized children."""

    handler: ContainerHandler

    def run(self) -> UnpackResult:
        """Unpack the container and list its children. Worker-side."""
        try:
            children = list(self.handler.walk())
            return UnpackResult(handler=self.handler, children=children)
        except Exception as exc:
            traceback.print_exc()
            return UnpackResult(handler=self.handler, children=[], exc=exc)


@dataclass
class OptimizeLeafJob:
    """Run handler.optimize_wrapper() in a worker; return ReportStats."""

    handler: ImageHandler
    path_info: PathInfo  # kept so main thread can hydrate it from result.data

    def run(self) -> ReportStats:
        """Optimize one leaf. Worker-side."""
        # optimize_wrapper() already catches Exception and returns a
        # ReportStats(exc=...). It never raises under normal paths.
        return self.handler.optimize_wrapper()


@dataclass
class RepackJob:
    """Run handler.repack() in a worker; return ReportStats."""

    handler: ContainerHandler

    def run(self) -> ReportStats:
        """Repack a container. Worker-side."""
        try:
            return self.handler.repack()
        except Exception as exc:
            traceback.print_exc()
            return self.handler.error(exc)


Job = UnpackJob | OptimizeLeafJob | RepackJob


# --------------------------------------------------------------------- nodes


@dataclass(eq=False)
class ContainerNode:
    """Bookkeeping for one container in the job tree."""

    handler: ContainerHandler
    parent: ContainerNode | None = None
    pending: int = 0
    children: list[ContainerNode] = field(default_factory=list)
    state: NodeState = NodeState.NEW
    had_work: bool = False  # any child produced replacement bytes
    staging_dir: Path | None = None

    def is_top_level(self: ContainerNode) -> bool:
        """Return True if this node has no container parent."""
        return self.parent is None


# ---------------------------------------------------------- leaf tracking


@dataclass
class _LeafEntry:
    """What the scheduler tracks per in-flight OptimizeLeafJob future."""

    job: OptimizeLeafJob
    parent: ContainerNode | None  # None = direct directory leaf, not in container


@dataclass
class _DirTracker:
    """Track pending children of a walked directory for timestamp writes."""

    top_path: Path
    pending: int = 0
    sealed: bool = False


# ------------------------------------------------------------------- scheduler


class Scheduler:
    """
    Main-thread scheduler loop.

    Owns the ProcessPoolExecutor, the ready deque, the inflight map, and the
    set of live ContainerNodes. Everything that used to live in
    walk._finish_results / walk._handle_container / walk._walk_container /
    container.optimize_contents lands here.
    """

    def __init__(
        self: Scheduler,
        *,
        config: AttrDict,
        executor: ProcessPoolExecutor,
        timestamps: Grovestamps | None,
        totals: Totals,
        printer: Printer,
        max_workers: int,
        create_repack_handler: Callable[[AttrDict, ContainerHandler], ContainerHandler],
        child_enqueue_callback: Callable[
            [Scheduler, ContainerNode, list[PathInfo]], None
        ],
    ) -> None:
        """Initialize scheduler state."""
        self._config = config
        self._executor = executor
        self._timestamps = timestamps
        self._totals = totals
        self._printer = printer
        self._max_workers = max_workers
        self._create_repack_handler = create_repack_handler
        self._child_enqueue_callback = child_enqueue_callback

        self._ready: deque[tuple[Job, ContainerNode | None]] = deque()
        self._inflight_unpack: dict[Future, ContainerNode] = {}
        self._inflight_leaf: dict[Future, _LeafEntry] = {}
        self._inflight_repack: dict[Future, ContainerNode] = {}
        self._live_nodes: set[ContainerNode] = set()

        self._dir_trackers: dict[Path, _DirTracker] = {}
        self._fail_fast_triggered: bool = False

    # ---------------------------------------------------------- public API
    def enqueue_leaf(
        self: Scheduler, job: OptimizeLeafJob, parent: ContainerNode | None = None
    ) -> None:
        """Enqueue a top-level or in-container leaf job."""
        self._ready.append((job, parent))
        if parent is not None:
            parent.pending += 1
        elif job.path_info.path is not None:
            self._dir_enqueue(job.path_info.path)

    def enqueue_container(
        self: Scheduler, handler: ContainerHandler, parent: ContainerNode | None = None
    ) -> ContainerNode:
        """Create a node for a container and enqueue its UnpackJob."""
        node = ContainerNode(handler=handler, parent=parent)
        self._live_nodes.add(node)
        if parent is not None:
            parent.children.append(node)
            parent.pending += 1
        elif handler.path_info.path is not None:
            self._dir_enqueue(handler.path_info.path)
        self._ready.append((UnpackJob(handler=handler), node))
        return node

    def accept_prebuilt_report(self, report: ReportStats, top_path: Path) -> None:
        """
        Accept a ReportStats built on the main thread.

        Used for the walk_file()-level exception path where the handler
        couldn't even be constructed. Routes through the same totals and
        timestamp write as a worker-produced result.
        """
        self._record_totals(report)
        self._write_timestamp(report, top_path)

    def begin_dir(self: Scheduler, top_path: Path, dir_path: Path) -> None:
        """Register a directory whose children are about to be enqueued."""
        parent_tracker = self._dir_trackers.get(dir_path.parent)
        if parent_tracker is not None:
            parent_tracker.pending += 1
        self._dir_trackers[dir_path] = _DirTracker(top_path=top_path)

    def seal_dir(self: Scheduler, dir_path: Path) -> None:
        """Mark a directory as fully enumerated; finalize if no pending children."""
        tracker = self._dir_trackers.get(dir_path)
        if tracker is None:
            return
        tracker.sealed = True
        if tracker.pending <= 0:
            self._finalize_dir(dir_path, tracker)

    def cancel_dir(self, dir_path: Path) -> None:
        """Remove a directory tracker without finalizing (used on walk errors)."""
        tracker = self._dir_trackers.pop(dir_path, None)
        if tracker is None:
            return
        parent_dir = dir_path.parent
        if parent_dir in self._dir_trackers:
            self._dir_child_done(parent_dir)

    def run(self: Scheduler) -> None:
        """Drain ready and inflight until both are empty."""
        try:
            while self._ready or self._inflight_count() > 0:
                self._submit_ready()
                if self._inflight_count() == 0:
                    continue
                all_futs = list(
                    chain(
                        self._inflight_unpack,
                        self._inflight_leaf,
                        self._inflight_repack,
                    )
                )
                done, _ = wait(all_futs, return_when=FIRST_COMPLETED)
                for fut in done:
                    self._handle_completion(fut)
        finally:
            self._cleanup_all_staging()

    # ------------------------------------------------------- internals
    #
    def _inflight_count(self: Scheduler) -> int:
        """
        Total futures currently submitted across all job kinds.

        Used by the run() loop termination check and by _submit_ready()
        for the 2 * max_workers backpressure cap.
        """
        return (
            len(self._inflight_unpack)
            + len(self._inflight_leaf)
            + len(self._inflight_repack)
        )

    def _submit_ready_job(self: Scheduler) -> None:
        """Pop and submit one job from the ready dequeue."""
        job, node = self._ready.popleft()
        # Skip jobs whose owning node got cancelled while they were queued.
        if node is not None and node.state is NodeState.CANCELLED:
            match job:
                case UnpackJob() | RepackJob():
                    # node's own job — the cancel walk already decremented
                    # the parent counter, nothing to do.
                    pass
                case _:
                    node.pending = max(0, node.pending - 1)
            return
        fut = self._executor.submit(job.run)
        match job:
            case UnpackJob():
                assert node is not None
                node.state = NodeState.UNPACKING
                self._inflight_unpack[fut] = node
            case OptimizeLeafJob():
                self._inflight_leaf[fut] = _LeafEntry(job=job, parent=node)
                if node is not None and node.state is NodeState.NEW:
                    node.state = NodeState.OPTIMIZING
            case RepackJob():
                assert node is not None
                node.state = NodeState.REPACKING
                self._inflight_repack[fut] = node

    def _submit_ready(self: Scheduler) -> None:
        """Submit ready jobs up to the backpressure cap."""
        cap = 2 * self._max_workers
        while self._ready and self._inflight_count() < cap:
            self._submit_ready_job()

    def _cancel_subtree(
        self: Scheduler, root: ContainerNode, *, reason: Exception
    ) -> None:
        """Mark a subtree CANCELLED, purge its ready work, clean staging."""
        del reason  # recorded by the caller in totals
        stack: list[ContainerNode] = [root]
        cancelled: set[ContainerNode] = set()
        while stack:
            node = stack.pop()
            if node in cancelled:
                continue
            cancelled.add(node)
            node.state = NodeState.CANCELLED
            node.handler.get_optimized_contents().clear()
            stack.extend(node.children)
        # Purge ready queue of anything belonging to a cancelled node.
        self._ready = deque((job, n) for (job, n) in self._ready if n not in cancelled)
        # Clean staging immediately for every cancelled node.
        for node in cancelled:
            self._cleanup_node_staging(node)
            self._live_nodes.discard(node)
        # Already-running futures check state on completion and drop results.

    def _trigger_fail_fast(self, reason: Exception) -> None:
        """Mark fail_fast, cancel every live top-level subtree."""
        self._fail_fast_triggered = True
        tops = [n for n in list(self._live_nodes) if n.is_top_level()]
        for top in tops:
            self._cancel_subtree(top, reason=reason)
        self._ready.clear()

    def _handle_completion(self: Scheduler, fut: Future) -> None:
        """Dispatch one completed future by which inflight map owns it."""
        if fut in self._inflight_unpack:
            node = self._inflight_unpack.pop(fut)
            exc = fut.exception()
            if exc is not None and isinstance(exc, Exception):
                self._handle_unpack_done(
                    node, UnpackResult(handler=node.handler, children=[], exc=exc)
                )
            else:
                self._handle_unpack_done(node, fut.result())
        elif fut in self._inflight_leaf:
            entry = self._inflight_leaf.pop(fut)
            exc = fut.exception()
            if exc is not None:
                report = ReportStats(
                    entry.job.path_info.path or entry.job.handler.original_path,
                    exc=exc,
                )
            else:
                report = fut.result()
            self._handle_leaf_done(entry, report)
        elif fut in self._inflight_repack:
            node = self._inflight_repack.pop(fut)
            exc = fut.exception()
            if exc is not None:
                report = ReportStats(node.handler.original_path, exc=exc)
            else:
                report = fut.result()
            self._handle_repack_done(node, report)

    def _handle_unpack_done(
        self: Scheduler, node: ContainerNode, result: UnpackResult
    ) -> None:
        """Process an UnpackJob completion."""
        # Replace the pre-walk handler with its pickle-roundtripped,
        # walk()-mutated twin. See UnpackResult docstring for which
        # attributes this restores.
        node.handler = result.handler

        if node.state is NodeState.CANCELLED:
            self._cleanup_node_staging(node)
            return

        if result.exc is not None:
            # Unpack itself blew up. Treat the whole container as one error,
            # notify parent, clean up, move on. (fail_fast variants handled
            # uniformly by _cancel_subtree / _trigger_fail_fast on repack
            # failures; unpack failures just mark this node DONE-with-error.)
            report = ReportStats(node.handler.original_path, exc=result.exc)
            self._handle_repack_done(node, report)  # reuses finalize path
            return

        # Hand children to the walk layer so it can create handlers and
        # enqueue them back against this node as parent.
        self._child_enqueue_callback(self, node, result.children)
        if node.pending == 0:
            node.state = NodeState.OPTIMIZING
            self._maybe_start_repack(node)
        else:
            node.state = NodeState.OPTIMIZING

    def _handle_leaf_done(
        self: Scheduler, entry: _LeafEntry, report: ReportStats
    ) -> None:
        """Process an OptimizeLeafJob completion."""
        parent = entry.parent

        # In-container leaf: hydrate PathInfo from bytes, stash in parent.
        if parent is not None:
            if parent.state is NodeState.CANCELLED:
                # drop on the floor, but still decrement so parent can
                # eventually finalize (its own cancel walk will handle it)
                parent.pending = max(0, parent.pending - 1)
                return
            if report.exc is None:
                parent.handler.hydrate_optimized_path_info(entry.job.path_info, report)
                parent.handler.get_optimized_contents().add(entry.job.path_info)
                if report.changed:
                    parent.had_work = True
            else:
                # leaf error inside a container — record, keep going
                self._totals.errors.append(report)
                report.report(self._printer)
            parent.pending = max(0, parent.pending - 1)
            self._maybe_start_repack(parent)
            return

        # Top-level directory leaf: straight to totals + timestamps.
        self._record_totals(report)
        self._write_timestamp(report, entry.job.path_info.top_path)
        if entry.job.path_info.path is not None:
            self._dir_child_done(entry.job.path_info.path.parent)

    def _handle_repack_failure(
        self: Scheduler, report: ReportStats, node: ContainerNode
    ) -> None:
        if self._config.fail_fast:
            self._totals.errors.append(report)
            report.report(self._printer)
            self._trigger_fail_fast(report.exc)
            return
        if self._config.fail_fast_container:
            # escalate to top-level container of this subtree
            root = node
            while root.parent is not None:
                root = root.parent
            self._cancel_subtree(root, reason=report.exc)
            self._totals.errors.append(report)
            report.report(self._printer)
            return
        # default rollback: this container becomes one error, parent
        # sees it as a "done" child with no work.
        self._cancel_subtree(node, reason=report.exc)
        self._totals.errors.append(report)
        report.report(self._printer)
        if node.parent is not None:
            node.parent.pending = max(0, node.parent.pending - 1)
            self._maybe_start_repack(node.parent)

    def _handle_repack_done(
        self: Scheduler, node: ContainerNode, report: ReportStats
    ) -> None:
        """Process a RepackJob completion (or synthesized no-op/error)."""
        if node.state is NodeState.CANCELLED:
            self._cleanup_node_staging(node)
            self._live_nodes.discard(node)
            return

        # Failure branches
        if report.exc is not None:
            self._handle_repack_failure(report, node)
            return

        # Success: accumulate, timestamp, cleanup, notify parent.
        self._record_totals(report)
        if node.is_top_level():
            top_path = node.handler.path_info.top_path
            self._write_timestamp(report, top_path)
            self._cleanup_node_staging(node)
            if node.handler.path_info.path is not None:
                self._dir_child_done(node.handler.path_info.path.parent)
        else:
            # Hydrate a PathInfo for our parent's _optimized_contents so
            # the parent's repack picks up our repacked bytes.
            parent = node.parent
            assert parent is not None
            if report.data:
                node.handler.path_info.set_data(report.data)
            parent.handler.get_optimized_contents().add(node.handler.path_info)
            if report.changed:
                parent.had_work = True
            # Our staging lives until the PARENT's repack reads us, so we
            # don't rmtree here. Parent's repack completion triggers it.
            parent.pending = max(0, parent.pending - 1)
            self._maybe_start_repack(parent)

        node.state = NodeState.DONE
        self._live_nodes.discard(node)
        # Clean up child staging dirs now that we've finished repacking.
        for child in node.children:
            # node.children is all ContainerNodes no check needed
            self._cleanup_node_staging(child)

    def _maybe_start_repack(self: Scheduler, node: ContainerNode) -> None:
        """If pending == 0, enqueue RepackJob or synthesize no-op completion."""
        if node.pending != 0 or node.state is NodeState.CANCELLED:
            return
        if node.state in (NodeState.REPACKING, NodeState.DONE):
            return

        # Respect the handler's own _do_repack flag (set during walk) OR
        # whether any child produced replacement bytes. Handlers like
        # Img2WebPAnimated set _do_repack=True unconditionally during walk()
        # because format conversion always requires repacking even when no
        # individual child was "optimized".
        if not node.handler.is_do_repack():
            node.handler.set_do_repack(do_repack=node.had_work)
        if not node.handler.is_do_repack():
            # No work: synthesize a no-op completion so the parent chain
            # gets notified identically to a real repack.
            noop = ReportStats(
                node.handler.original_path,
                bytes_in=node.handler.path_info.bytes_in(),
                bytes_out=node.handler.path_info.bytes_in(),
                changed=False,
            )
            self._handle_repack_done(node, noop)
            return

        node.handler.clean_for_repack()
        repack_handler = self._create_repack_handler(self._config, node.handler)
        node.handler = repack_handler
        self._ready.append((RepackJob(handler=repack_handler), node))

    def _record_totals(self: Scheduler, report: ReportStats) -> None:
        """Accumulate one ReportStats into Totals."""
        if report.exc:
            self._totals.errors.append(report)
            report.report(self._printer)
            return
        self._totals.bytes_in += report.bytes_in
        if report.saved > 0 and not self._config.bigger:
            self._totals.bytes_out += report.bytes_out
        else:
            self._totals.bytes_out += report.bytes_in

    def _write_timestamp(self: Scheduler, report: ReportStats, top_path: Path) -> None:
        """Write a timestamp if timestamps are enabled and no error."""
        if self._timestamps and report.path is not None and not report.exc:
            self._timestamps.set(top_path, report.path)

    def _dir_enqueue(self: Scheduler, child_path: Path) -> None:
        """Increment a directory's pending count for a newly enqueued child."""
        tracker = self._dir_trackers.get(child_path.parent)
        if tracker is not None:
            tracker.pending += 1

    def _dir_child_done(self: Scheduler, parent_dir: Path) -> None:
        """Decrement a directory's pending count; finalize when ready."""
        tracker = self._dir_trackers.get(parent_dir)
        if tracker is None:
            return
        tracker.pending -= 1
        if tracker.pending <= 0 and tracker.sealed:
            self._finalize_dir(parent_dir, tracker)

    def _finalize_dir(self: Scheduler, dir_path: Path, tracker: _DirTracker) -> None:
        """Write directory timestamp with compaction and cascade to parent."""
        del self._dir_trackers[dir_path]
        if self._timestamps:
            self._timestamps.set(tracker.top_path, dir_path, compact=True)
        parent_dir = dir_path.parent
        if parent_dir in self._dir_trackers:
            self._dir_child_done(parent_dir)

    def _cleanup_node_staging(self: Scheduler, node: ContainerNode) -> None:
        """Rmtree this node's staging_dir, swallowing errors."""
        if node.staging_dir is None:
            return
        try:
            shutil.rmtree(node.staging_dir, ignore_errors=True)
        except Exception:
            traceback.print_exc()
        node.staging_dir = None

    def _cleanup_all_staging(self: Scheduler) -> None:
        """Emergency cleanup: rmtree every live node's staging dir."""
        for node in list(self._live_nodes):
            self._cleanup_node_staging(node)
