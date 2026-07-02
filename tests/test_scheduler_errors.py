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

    def __init__(
        self, name: str, path: Path | None = None, top_path: Path | None = None
    ) -> None:
        self._name = name
        self.path: Path | None = path
        self.top_path: Path | None = top_path

    def bytes_in(self) -> int:
        return 100


class _FakeContainerHandler:
    """Minimal ContainerHandler stand-in for completion handling."""

    def __init__(self, name: str) -> None:
        self.path_info = _FakePathInfo(name)
        self.original_path = Path(name)
        self.repack_handler_class = None
        self.hydrate_calls: list[tuple[Any, Any]] = []
        self._optimized_contents: set[Any] = set()
        self._do_repack = False

    def get_optimized_contents(self) -> set[Any]:
        return self._optimized_contents

    def is_do_repack(self) -> bool:
        return self._do_repack

    def set_do_repack(self, *, do_repack: bool) -> None:
        self._do_repack = do_repack

    def hydrate_optimized_path_info(self, path_info: Any, report: Any) -> None:
        self.hydrate_calls.append((path_info, report))


class _FakeReporter:
    """Records every report it is handed."""

    def __init__(self) -> None:
        self.reports: list[ReportStats] = []

    def record_report(self, report: ReportStats) -> None:
        self.reports.append(report)


class _FakeTimestamps:
    """Records every timestamp set() call."""

    def __init__(self) -> None:
        self.set_calls: list[tuple] = []

    def set(self, *args, **kwargs) -> None:
        self.set_calls.append((args, kwargs))


def _make_scheduler() -> tuple[Scheduler, _FakeReporter, _FakeTimestamps]:
    args = cli.get_arguments(("picopt", "."))
    config = PicoptConfig().get_config(args)
    reporter = _FakeReporter()
    timestamps = _FakeTimestamps()
    scheduler = Scheduler(
        config=config,
        executor=None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        timestamps=timestamps,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        reporter=reporter,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        max_workers=1000,
        create_repack_handler=lambda _config, handler: handler,
        child_enqueue_callback=lambda *_a: None,
    )
    return scheduler, reporter, timestamps


class TestSchedulerErrorPaths:
    """Errored members must be preserved in their parent container."""

    def test_errored_leaf_kept_in_parent_contents(self: Any) -> None:
        """A member whose optimization errors stays in the repacked archive."""
        scheduler, reporter, _ = _make_scheduler()
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
        assert parent.had_error
        assert any(r.exc for r in reporter.reports)

    def test_failed_nested_repack_kept_in_parent_contents(self: Any) -> None:
        """A nested container whose repack fails stays in the parent archive."""
        scheduler, reporter, _ = _make_scheduler()
        parent_handler = _FakeContainerHandler(str(_ARCHIVE_PATH))
        parent = scheduler.enqueue_container(parent_handler)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

        child_handler = _FakeContainerHandler("nested.cbz")
        child = scheduler.enqueue_container(child_handler, parent)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        assert parent.pending == 1

        report = ReportStats(Path("nested.cbz"), exc=ValueError("repack failed"))
        scheduler._handle_repack_done(child, report)

        assert child_handler.path_info in parent_handler.get_optimized_contents()
        assert parent.pending == 0
        assert parent.had_error
        assert any(r.exc for r in reporter.reports)


class TestDirTimestampsOnError:
    """Directories and containers with errored children must not be stamped."""

    def test_errored_leaf_poisons_dir_timestamp(self: Any, tmp_path: Path) -> None:
        """A failed file blocks the compacted dir stamp; successes don't."""
        scheduler, _, timestamps = _make_scheduler()
        scheduler.begin_dir(tmp_path, tmp_path)

        member_path = tmp_path / "bad.png"
        member_info = _FakePathInfo(str(member_path), path=member_path)
        job = OptimizeLeafJob(handler=None, path_info=member_info)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        scheduler.enqueue_leaf(job)

        report = ReportStats(member_path, exc=ValueError("boom"))
        scheduler._handle_leaf_done(_LeafEntry(job=job, parent=None), report)
        scheduler.seal_dir(tmp_path)

        assert tmp_path not in scheduler._dir_trackers
        assert not timestamps.set_calls

    def test_clean_dir_still_gets_compacted_timestamp(
        self: Any, tmp_path: Path
    ) -> None:
        """Without errors the dir stamp is written with compaction."""
        scheduler, _, timestamps = _make_scheduler()
        scheduler.begin_dir(tmp_path, tmp_path)

        member_path = tmp_path / "good.png"
        member_info = _FakePathInfo(str(member_path), path=member_path)
        job = OptimizeLeafJob(handler=None, path_info=member_info)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        scheduler.enqueue_leaf(job)

        report = ReportStats(member_path, bytes_in=10, bytes_out=5, changed=True)
        scheduler._handle_leaf_done(_LeafEntry(job=job, parent=None), report)
        scheduler.seal_dir(tmp_path)

        assert tmp_path not in scheduler._dir_trackers
        compacted = [c for c in timestamps.set_calls if c[1].get("compact")]
        assert compacted

    def test_failed_top_level_container_notifies_dir_tracker(
        self: Any, tmp_path: Path
    ) -> None:
        """A failed container repack must not leak its directory tracker."""
        scheduler, _, timestamps = _make_scheduler()
        scheduler.begin_dir(tmp_path, tmp_path)

        archive_path = tmp_path / "broken.cbz"
        handler = _FakeContainerHandler(str(archive_path))
        handler.path_info.path = archive_path
        node = scheduler.enqueue_container(handler)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

        report = ReportStats(archive_path, exc=ValueError("repack failed"))
        scheduler._handle_repack_done(node, report)
        scheduler.seal_dir(tmp_path)

        assert tmp_path not in scheduler._dir_trackers
        assert not timestamps.set_calls

    def test_container_with_errored_member_not_timestamped(
        self: Any, tmp_path: Path
    ) -> None:
        """A container whose member errored gets no timestamp on success."""
        scheduler, _, timestamps = _make_scheduler()
        archive_path = tmp_path / "partial.cbz"
        handler = _FakeContainerHandler(str(archive_path))
        handler.path_info.path = archive_path
        handler.path_info.top_path = tmp_path
        node = scheduler.enqueue_container(handler)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        node.had_error = True

        report = ReportStats(archive_path, bytes_in=10, bytes_out=5, changed=True)
        scheduler._handle_repack_done(node, report)

        assert not timestamps.set_calls


class TestNestedConversionRename:
    """Nested container repacks must hydrate renames onto the parent."""

    def test_nested_repack_success_hydrates_parent(self: Any) -> None:
        """The parent handler hydrates data and rename from the report."""
        scheduler, _, _ = _make_scheduler()
        parent_handler = _FakeContainerHandler(str(_ARCHIVE_PATH))
        parent = scheduler.enqueue_container(parent_handler)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        child_handler = _FakeContainerHandler("inner.cbr")
        child = scheduler.enqueue_container(child_handler, parent)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

        report = ReportStats(
            Path("inner.cbz"), bytes_in=10, bytes_out=5, changed=True, data=b"zipdata"
        )
        scheduler._handle_repack_done(child, report)

        assert parent_handler.hydrate_calls == [(child_handler.path_info, report)]
        assert child_handler.path_info in parent_handler.get_optimized_contents()
        assert parent.had_work
