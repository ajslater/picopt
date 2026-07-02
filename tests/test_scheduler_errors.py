"""Test that scheduler failure paths never drop archive members."""

from pathlib import Path
from typing import Any

from picopt import cli
from picopt.config import PicoptConfig
from picopt.report import ReportStats
from picopt.walk.scheduler import OptimizeLeafJob, Scheduler, _LeafEntry

__all__ = ()  # hides module from pydocstring

_MEMBER_PATH = Path("member.png")
_ARCHIVE_PATH = Path("test.cbz")


class _FakePathInfo:
    """Minimal PathInfo stand-in for error-path bookkeeping."""

    def __init__(self, name: str) -> None:
        self._name = name
        self.path = None
        self.top_path = None

    def bytes_in(self) -> int:
        return 100


class _FakeContainerHandler:
    """Minimal ContainerHandler stand-in for completion handling."""

    def __init__(self, name: str) -> None:
        self.path_info = _FakePathInfo(name)
        self.original_path = Path(name)
        self._optimized_contents: set[Any] = set()
        self._do_repack = False

    def get_optimized_contents(self) -> set[Any]:
        return self._optimized_contents

    def is_do_repack(self) -> bool:
        return self._do_repack

    def set_do_repack(self, *, do_repack: bool) -> None:
        self._do_repack = do_repack

    def hydrate_optimized_path_info(self, path_info: Any, report: Any) -> None:
        pass


class _FakeReporter:
    """Records every report it is handed."""

    def __init__(self) -> None:
        self.reports: list[ReportStats] = []

    def record_report(self, report: ReportStats) -> None:
        self.reports.append(report)


def _make_scheduler() -> tuple[Scheduler, _FakeReporter]:
    args = cli.get_arguments(("picopt", "."))
    config = PicoptConfig().get_config(args)
    reporter = _FakeReporter()
    scheduler = Scheduler(
        config=config,
        executor=None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        timestamps=None,
        reporter=reporter,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        max_workers=1000,
        create_repack_handler=lambda _config, handler: handler,
        child_enqueue_callback=lambda *_a: None,
    )
    return scheduler, reporter


class TestSchedulerErrorPaths:
    """Errored members must be preserved in their parent container."""

    def test_errored_leaf_kept_in_parent_contents(self: Any) -> None:
        """A member whose optimization errors stays in the repacked archive."""
        scheduler, reporter = _make_scheduler()
        parent_handler = _FakeContainerHandler(str(_ARCHIVE_PATH))
        parent = scheduler.enqueue_container(parent_handler)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

        member_info = _FakePathInfo(str(_MEMBER_PATH))
        job = OptimizeLeafJob(handler=None, path_info=member_info)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        scheduler.enqueue_leaf(job, parent)
        assert parent.pending == 1

        report = ReportStats(_MEMBER_PATH, exc=ValueError("simulated failure"))
        entry = _LeafEntry(job=job, parent=parent)
        scheduler._handle_leaf_done(entry, report)

        assert member_info in parent_handler.get_optimized_contents()
        assert parent.pending == 0
        assert any(r.exc for r in reporter.reports)

    def test_failed_nested_repack_kept_in_parent_contents(self: Any) -> None:
        """A nested container whose repack fails stays in the parent archive."""
        scheduler, reporter = _make_scheduler()
        parent_handler = _FakeContainerHandler(str(_ARCHIVE_PATH))
        parent = scheduler.enqueue_container(parent_handler)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

        child_handler = _FakeContainerHandler("nested.cbz")
        child = scheduler.enqueue_container(child_handler, parent)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        assert parent.pending == 1

        report = ReportStats(Path("nested.cbz"), exc=ValueError("repack failed"))
        scheduler._handle_repack_done(child, report)

        assert child_handler.path_info in parent_handler.get_optimized_contents()
        assert parent.pending == 0
        assert any(r.exc for r in reporter.reports)
