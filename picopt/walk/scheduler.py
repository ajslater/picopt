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
from picopt.walk.detect_format import predetect_format
from picopt.walk.dir_timestamps import DirTimestamper

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from treestamps import Grovestamps

    from picopt.config.settings import PicoptSettings
    from picopt.log.reporter import Reporter
    from picopt.path import PathInfo
    from picopt.plugins.base import ContainerHandler, ImageHandler


# --------------------------------------------------------------------- state

# Multiplier from a top-level item's on-disk size to its estimated peak resident
# memory while optimized. A container holds, concurrently: the whole archive
# bytes, every decompressed member, the optimized copies, and the output buffer
# built at repack — plus a pickled duplicate of much of that in the worker
# process. Measured peak RSS / on-disk size is ~3x for comic archives, so the
# sum of charges approximates real memory use and ``--memory-limit`` reads as an
# approximate RAM target. It only needs to be roughly right: the memory gate
# always lets a single over-budget item run alone, so an underestimate never
# deadlocks, it just overshoots once.
_MEM_COST_FACTOR = 3


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
    matter to the main thread:

    - staging dir path — read uniformly via ``get_staging_dir()`` and
      stored on the node. The main thread needs this to rmtree on
      cleanup or rollback.
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
            # Pre-detect member formats here so the expensive PIL sniff
            # parallelizes instead of serializing on the scheduler thread.
            keep_metadata = self.handler.config.keep_metadata
            for child in children:
                predetect_format(child, keep_metadata=keep_metadata)
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
    had_error: bool = False  # any child errored; don't timestamp this subtree
    staging_dir: Path | None = None
    cost: int = 0  # memory budget charged for this node (0 = not charged)

    def is_top_level(self) -> bool:
        """Return True if this node has no container parent."""
        return self.parent is None


# ---------------------------------------------------------- leaf tracking


@dataclass
class _LeafEntry:
    """What the scheduler tracks per in-flight OptimizeLeafJob future."""

    job: OptimizeLeafJob
    parent: ContainerNode | None  # None = direct directory leaf, not in container
    cost: int = 0  # memory budget charged for a standalone leaf (0 otherwise)


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
        self,
        *,
        config: PicoptSettings,
        executor: ProcessPoolExecutor,
        timestamps: Grovestamps | None,
        reporter: Reporter,
        max_workers: int,
        create_repack_handler: Callable[
            [PicoptSettings, ContainerHandler], ContainerHandler
        ],
        child_enqueue_callback: Callable[
            [Scheduler, ContainerNode, list[PathInfo]], None
        ],
    ) -> None:
        """Initialize scheduler state."""
        self._config = config
        self._executor = executor
        self._timestamps = timestamps
        self._reporter = reporter
        self._max_workers = max_workers
        self._create_repack_handler = create_repack_handler
        self._child_enqueue_callback = child_enqueue_callback

        self._ready: deque[tuple[Job, ContainerNode | None]] = deque()
        # Top-level items deferred by the memory gate wait here in FIFO
        # order instead of being re-scanned through _ready on every tick.
        self._gated: deque[tuple[Job, ContainerNode | None]] = deque()
        self._inflight_unpack: dict[Future, ContainerNode] = {}
        self._inflight_leaf: dict[Future, _LeafEntry] = {}
        self._inflight_repack: dict[Future, ContainerNode] = {}
        self._live_nodes: set[ContainerNode] = set()

        self._dirs = DirTimestamper(timestamps)
        self._fail_fast_triggered: bool = False

        # Memory-aware admission. `_byte_budget <= 0` disables the gate.
        # `_inflight_bytes` is the sum of estimated resident memory for every
        # live top-level item (containers still being unpacked/optimized/
        # repacked, plus standalone leaf images). New top-level items are only
        # admitted while they fit the budget — except when nothing is live, so a
        # single archive larger than the whole budget still runs (alone).
        self._byte_budget: int = config.memory_limit
        self._inflight_bytes: int = 0

    # ---------------------------------------------------------- public API
    def enqueue_leaf(
        self, job: OptimizeLeafJob, parent: ContainerNode | None = None
    ) -> None:
        """Enqueue a top-level or in-container leaf job."""
        self._ready.append((job, parent))
        if parent is not None:
            parent.pending += 1
        elif job.path_info.path is not None:
            self._dirs.enqueue_child(job.path_info.path)

    def enqueue_container(
        self, handler: ContainerHandler, parent: ContainerNode | None = None
    ) -> ContainerNode:
        """Create a node for a container and enqueue its UnpackJob."""
        node = ContainerNode(handler=handler, parent=parent)
        self._live_nodes.add(node)
        if parent is not None:
            parent.children.append(node)
            parent.pending += 1
        elif handler.path_info.path is not None:
            self._dirs.enqueue_child(handler.path_info.path)
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
        if report.exc and report.path is not None:
            self._dirs.mark_errored(report.path.parent)

    def begin_dir(self, top_path: Path, dir_path: Path) -> None:
        """Register a directory whose children are about to be enqueued."""
        self._dirs.begin_dir(top_path, dir_path)

    def seal_dir(self, dir_path: Path) -> None:
        """Mark a directory as fully enumerated; finalize if no pending children."""
        self._dirs.seal_dir(dir_path)

    def cancel_dir(self, dir_path: Path) -> None:
        """Remove a directory tracker without finalizing (used on walk errors)."""
        self._dirs.cancel_dir(dir_path)

    def run(self) -> None:
        """Drain ready, gated, and inflight until all are empty."""
        try:
            while self._ready or self._gated or self._inflight_count() > 0:
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
    def _inflight_count(self) -> int:
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

    def _drop_cancelled_ready_job(self, job: Job, node: ContainerNode) -> None:
        """
        Decrement parent pending counter for a leaf of a cancelled subtree.

        UnpackJob/RepackJob jobs belong to ``node`` itself; the cancel walk
        already decremented the parent's pending counter for them, so they
        need no further bookkeeping.
        """
        match job:
            case UnpackJob() | RepackJob():
                pass
            case _:
                self._child_done(node)

    def _track_submitted_job(
        self, fut: Future, job: Job, node: ContainerNode | None
    ) -> None:
        """Record an in-flight future under the right map and update state."""
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

    def _est_cost(self, path_info: PathInfo) -> int:
        """Estimate peak resident memory for a top-level item, in bytes."""
        return int(path_info.bytes_in()) * _MEM_COST_FACTOR

    def _charge_info(self, job: Job, node: ContainerNode | None) -> tuple[bool, int]:
        """
        Whether a ready job introduces a *new* top-level item, and its cost.

        Only new top-level containers (their UnpackJob) and standalone
        directory-level leaves are charged/gated. Jobs that make progress on an
        already-admitted container (in-container leaves, nested-container
        unpacks, and every RepackJob) are exempt — their memory is already
        accounted for by their top-level ancestor, and gating them could
        deadlock the container that must repack to release budget.
        """
        match job:
            case UnpackJob():
                if node is not None and node.is_top_level():
                    return True, self._est_cost(node.handler.path_info)
            case OptimizeLeafJob():
                if node is None:  # standalone directory leaf
                    return True, self._est_cost(job.path_info)
            case _:  # RepackJob and progress on already-admitted containers
                pass
        return False, 0

    def _admits(self, cost: int) -> bool:
        """Whether a new top-level item costing `cost` may start now."""
        if self._byte_budget <= 0:
            return True  # gate disabled
        if self._inflight_bytes == 0:
            return True  # forward-progress guarantee: run it alone
        return self._inflight_bytes + cost <= self._byte_budget

    def _release_budget(self, cost: int) -> None:
        self._inflight_bytes = max(0, self._inflight_bytes - cost)

    def _retire_node(self, node: ContainerNode) -> None:
        """Release a node's memory charge and drop it from the live set."""
        self._release_budget(node.cost)
        node.cost = 0
        self._live_nodes.discard(node)

    def _submit_one(self, job: Job, node: ContainerNode | None, cost: int) -> None:
        """Submit one admitted job and charge its budget (if any)."""
        fut = self._executor.submit(job.run)
        self._track_submitted_job(fut, job, node)
        if cost:
            self._inflight_bytes += cost
            if isinstance(job, UnpackJob):
                assert node is not None
                node.cost = cost
            else:  # standalone leaf
                self._inflight_leaf[fut].cost = cost

    def _submit_gated(self, cap: int) -> None:
        """Admit memory-gated items in FIFO order until the head blocks."""
        while self._gated and self._inflight_count() < cap:
            job, node = self._gated[0]
            if node is not None and node.state is NodeState.CANCELLED:
                self._gated.popleft()
                self._drop_cancelled_ready_job(job, node)
                continue
            _, cost = self._charge_info(job, node)
            if not self._admits(cost):
                break
            self._gated.popleft()
            self._submit_one(job, node, cost)

    def _submit_ready(self) -> None:
        """
        Submit ready jobs up to the backpressure cap and the memory budget.

        Top-level items blocked by the memory budget move to the gated
        queue so exempt jobs behind them (leaves/repacks of already-admitted
        containers) still run — those are what eventually complete and free
        budget. The gated queue is retried head-first each tick instead of
        rescanning the whole ready queue.
        """
        cap = 2 * self._max_workers
        self._submit_gated(cap)
        while self._ready and self._inflight_count() < cap:
            job, node = self._ready.popleft()
            # Skip jobs whose owning node got cancelled while they were queued.
            if node is not None and node.state is NodeState.CANCELLED:
                self._drop_cancelled_ready_job(job, node)
                continue
            charged, cost = self._charge_info(job, node)
            if charged and not self._admits(cost):
                self._gated.append((job, node))
                continue
            self._submit_one(job, node, cost if charged else 0)

    def _cancel_subtree(
        self, root: ContainerNode, *, reason: BaseException | None
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
        # Purge queues of anything belonging to a cancelled node.
        self._ready = deque((job, n) for (job, n) in self._ready if n not in cancelled)
        self._gated = deque((job, n) for (job, n) in self._gated if n not in cancelled)
        # Clean staging immediately for every cancelled node.
        for node in cancelled:
            self._cleanup_node_staging(node)
            self._retire_node(node)
        # Already-running futures check state on completion and drop results.

    def _trigger_fail_fast(self, reason: BaseException | None) -> None:
        """Mark fail_fast, cancel every live top-level subtree."""
        self._fail_fast_triggered = True
        tops = [n for n in list(self._live_nodes) if n.is_top_level()]
        for top in tops:
            self._cancel_subtree(top, reason=reason)
        self._ready.clear()
        self._gated.clear()

    def _handle_completion(self, fut: Future) -> None:
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

    def _handle_unpack_done(self, node: ContainerNode, result: UnpackResult) -> None:
        """Process an UnpackJob completion."""
        # Replace the pre-walk handler with its pickle-roundtripped,
        # walk()-mutated twin. See UnpackResult docstring for which
        # attributes this restores.
        node.handler = result.handler
        node.staging_dir = result.handler.get_staging_dir()

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

    def _handle_leaf_done(self, entry: _LeafEntry, report: ReportStats) -> None:
        """Process an OptimizeLeafJob completion."""
        # Release a standalone leaf's memory charge (0 for in-container leaves).
        self._release_budget(entry.cost)
        parent = entry.parent

        # In-container leaf: hydrate PathInfo from bytes, stash in parent.
        if parent is not None:
            if parent.state is NodeState.CANCELLED:
                # drop on the floor, but still decrement so parent can
                # eventually finalize (its own cancel walk will handle it)
                self._child_done(parent)
                return
            if report.exc is None:
                parent.handler.hydrate_optimized_path_info(entry.job.path_info, report)
                parent.handler.get_optimized_contents().add(entry.job.path_info)
                if report.changed:
                    parent.had_work = True
            else:
                # leaf error inside a container — record it, but keep the
                # member's walk-time bytes so repack doesn't drop it from
                # the rebuilt archive.
                self._reporter.record_report(report)
                parent.handler.get_optimized_contents().add(entry.job.path_info)
                parent.had_error = True
            self._child_done(parent)
            return

        # Top-level directory leaf: straight to totals + timestamps.
        self._record_totals(report)
        self._write_timestamp(report, entry.job.path_info.top_path)
        if entry.job.path_info.path is not None:
            self._dirs.child_done(
                entry.job.path_info.path.parent, errored=bool(report.exc)
            )

    def _handle_repack_failure(self, report: ReportStats, node: ContainerNode) -> None:
        if self._config.fail_fast:
            self._reporter.record_report(report)
            self._trigger_fail_fast(report.exc)
            return
        if self._config.fail_fast_container:
            # escalate to top-level container of this subtree
            root = node
            while root.parent is not None:
                root = root.parent
            self._cancel_subtree(root, reason=report.exc)
            self._reporter.record_report(report)
            self._notify_dir_of_top_level_error(root)
            return
        # default rollback: this container becomes one error, parent
        # sees it as a "done" child with no work.
        self._cancel_subtree(node, reason=report.exc)
        self._reporter.record_report(report)
        if node.parent is not None:
            # Keep the nested container's original bytes so the parent's
            # repack doesn't drop this member from the rebuilt archive.
            node.parent.handler.get_optimized_contents().add(node.handler.path_info)
            node.parent.had_error = True
            self._child_done(node.parent)
        else:
            self._notify_dir_of_top_level_error(node)

    def _notify_dir_of_top_level_error(self, node: ContainerNode) -> None:
        """Tell a failed top-level container's directory tracker it is done."""
        path = node.handler.path_info.path
        if path is not None:
            self._dirs.child_done(path.parent, errored=True)

    def _handle_repack_done(self, node: ContainerNode, report: ReportStats) -> None:
        """Process a RepackJob completion (or synthesized no-op/error)."""
        if node.state is NodeState.CANCELLED:
            self._cleanup_node_staging(node)
            self._retire_node(node)
            return

        # Failure branches
        if report.exc is not None:
            self._handle_repack_failure(report, node)
            return

        # Success: accumulate, timestamp, cleanup, notify parent.
        self._record_totals(report)
        if node.is_top_level():
            top_path = node.handler.path_info.top_path
            # A member error inside means the container isn't fully
            # optimized; timestamping it would skip the failed member
            # forever on subsequent runs.
            if not node.had_error:
                self._write_timestamp(report, top_path)
            self._cleanup_node_staging(node)
            if node.handler.path_info.path is not None:
                self._dirs.child_done(
                    node.handler.path_info.path.parent, errored=node.had_error
                )
        else:
            # Hydrate a PathInfo for our parent's _optimized_contents so
            # the parent's repack picks up our repacked bytes and any
            # conversion rename (performed on the worker's pickled copy).
            parent = node.parent
            assert parent is not None
            parent.handler.hydrate_optimized_path_info(node.handler.path_info, report)
            parent.handler.get_optimized_contents().add(node.handler.path_info)
            if report.changed:
                parent.had_work = True
            if node.had_error:
                parent.had_error = True
            # Our staging lives until the PARENT's repack reads us, so we
            # don't rmtree here. Parent's repack completion triggers it.
            self._child_done(parent)

        node.state = NodeState.DONE
        self._retire_node(node)
        # Clean up child staging dirs now that we've finished repacking.
        for child in node.children:
            # node.children is all ContainerNodes no check needed
            self._cleanup_node_staging(child)

    def _child_done(self, node: ContainerNode) -> None:
        """
        One child of ``node`` finished (or was dropped); maybe repack.

        The single place a container's pending counter decrements.
        _maybe_start_repack() itself refuses cancelled/repacking/done
        nodes, so this is safe on every completion path.
        """
        node.pending = max(0, node.pending - 1)
        self._maybe_start_repack(node)

    def _maybe_start_repack(self, node: ContainerNode) -> None:
        """If pending == 0, enqueue RepackJob or synthesize no-op completion."""
        if node.pending != 0 or node.state is NodeState.CANCELLED:
            return
        if node.state in (NodeState.REPACKING, NodeState.DONE):
            return

        # Respect the handler's own _do_repack flag (set during walk) OR
        # whether any child produced replacement bytes. Handlers like
        # Img2WebPAnimated set _do_repack=True unconditionally during walk()
        # because format conversion always requires repacking even when no
        # individual child was "optimized". A requested container format
        # conversion (e.g. CBR -> CBZ) also needs a repack even when every
        # member was already optimized.
        if not node.handler.is_do_repack():
            convert_intent = (
                node.handler.repack_handler_class is not None
                and type(node.handler) is not node.handler.repack_handler_class
            )
            node.handler.set_do_repack(do_repack=node.had_work or convert_intent)
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

        repack_handler = self._create_repack_handler(self._config, node.handler)
        node.handler = repack_handler
        self._ready.append((RepackJob(handler=repack_handler), node))

    def _record_totals(self, report: ReportStats) -> None:
        """Hand one ReportStats off to the Reporter for stats + progress + log."""
        self._reporter.record_report(report)

    def _write_timestamp(self, report: ReportStats, top_path: Path) -> None:
        """Write a timestamp if timestamps are enabled and no error."""
        if self._timestamps and report.path is not None and not report.exc:
            self._timestamps.set(top_path, report.path)

    def _cleanup_node_staging(self, node: ContainerNode) -> None:
        """Rmtree this node's staging_dir, swallowing errors."""
        if node.staging_dir is None:
            return
        try:
            shutil.rmtree(node.staging_dir, ignore_errors=True)
        except Exception:
            traceback.print_exc()
        node.staging_dir = None

    def _cleanup_all_staging(self) -> None:
        """Emergency cleanup: rmtree every live node's staging dir."""
        for node in list(self._live_nodes):
            self._cleanup_node_staging(node)
