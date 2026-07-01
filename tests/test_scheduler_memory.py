"""Test the scheduler's memory-aware admission gate."""

from typing import Any

from picopt import cli
from picopt.config import PicoptConfig
from picopt.walk.scheduler import _MEM_COST_FACTOR, Scheduler

__all__ = ()  # hides module from pydocstring

# Each container of on-disk size S is charged S * _MEM_COST_FACTOR.
_SIZE = 100
_COST = _SIZE * _MEM_COST_FACTOR
_FITS = 2  # how many such containers fit the budget together
_BUDGET = _COST * _FITS  # budget sized to admit exactly _FITS at once
_TOTAL = 3  # containers enqueued
_DEFERRED = _TOTAL - _FITS
_ALL = 5
_NONE = 0
_BIG_SIZE = _BUDGET  # one container whose cost far exceeds the whole budget


class _FakePathInfo:
    """Minimal PathInfo stand-in exposing only what the gate reads."""

    def __init__(self, size: int) -> None:
        self._size = size
        self.path = None

    def bytes_in(self) -> int:
        return self._size


class _FakeHandler:
    """Minimal ContainerHandler stand-in with a sized path_info."""

    def __init__(self, size: int) -> None:
        self.path_info = _FakePathInfo(size)


class _StubExecutor:
    """Records submissions and returns opaque futures that never run."""

    def __init__(self) -> None:
        self.submitted: list[Any] = []

    def submit(self, fn: Any) -> object:
        self.submitted.append(fn)
        return object()


def _make_scheduler(memory_limit_bytes: int) -> "tuple[Scheduler, _StubExecutor]":
    args = cli.get_arguments(("picopt", "--memory-limit", str(memory_limit_bytes), "."))
    config = PicoptConfig().get_config(args)
    executor = _StubExecutor()
    scheduler = Scheduler(
        config=config,
        executor=executor,  # type: ignore[arg-type]
        timestamps=None,
        reporter=None,  # type: ignore[arg-type]
        max_workers=1000,  # keep the 2*max_workers future cap out of the way
        create_repack_handler=lambda *_a: None,  # type: ignore[arg-type,return-value]
        child_enqueue_callback=lambda *_a: None,
    )
    return scheduler, executor


class TestSchedulerMemoryGate:
    """Test memory-budget admission control."""

    def test_gate_admits_within_budget(self: Any) -> None:
        """Only as many large containers as fit the budget start at once."""
        scheduler, executor = _make_scheduler(_BUDGET)
        for _ in range(_TOTAL):
            scheduler.enqueue_container(_FakeHandler(_SIZE))  # type: ignore[arg-type]
        scheduler._submit_ready()
        assert len(executor.submitted) == _FITS
        assert scheduler._inflight_bytes == _COST * _FITS
        assert len(scheduler._ready) == _DEFERRED

    def test_gate_runs_oversized_item_alone(self: Any) -> None:
        """A single item bigger than the whole budget still runs (alone)."""
        scheduler, executor = _make_scheduler(_BUDGET)
        scheduler.enqueue_container(_FakeHandler(_BIG_SIZE))  # type: ignore[arg-type]
        scheduler._submit_ready()
        assert len(executor.submitted) == 1
        assert scheduler._inflight_bytes == _BIG_SIZE * _MEM_COST_FACTOR

    def test_retiring_a_node_frees_budget(self: Any) -> None:
        """A deferred item is admitted once an in-flight node retires."""
        scheduler, executor = _make_scheduler(_BUDGET)
        nodes = [
            scheduler.enqueue_container(_FakeHandler(_SIZE))  # type: ignore[arg-type]
            for _ in range(_TOTAL)
        ]
        scheduler._submit_ready()
        assert len(scheduler._ready) == _DEFERRED

        admitted = [node for node in nodes if node.cost > 0]
        scheduler._retire_node(admitted[0])
        assert scheduler._inflight_bytes == _COST * (_FITS - 1)

        scheduler._submit_ready()
        assert len(executor.submitted) == _TOTAL
        assert len(scheduler._ready) == _NONE

    def test_large_budget_admits_everything(self: Any) -> None:
        """A generous budget never defers work."""
        scheduler, executor = _make_scheduler(1024**4)  # 1 TiB
        for _ in range(_ALL):
            scheduler.enqueue_container(_FakeHandler(_SIZE))  # type: ignore[arg-type]
        scheduler._submit_ready()
        assert len(executor.submitted) == _ALL
        assert len(scheduler._ready) == _NONE
