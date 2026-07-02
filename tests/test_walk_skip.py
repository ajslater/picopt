"""Test walk skip rules and per-member error resilience."""

import os
from pathlib import Path
from typing import Any

import pytest
from treestamps import Treestamps

from picopt import PROGRAM_NAME, cli
from picopt.config import PicoptConfig
from picopt.config.settings import PicoptSettings
from picopt.log.reporter import Reporter
from picopt.path import PathInfo
from picopt.walk.scheduler import ContainerNode
from picopt.walk.skip import WalkSkipper
from picopt.walk.walk import Walk

__all__ = ()

_DATA = b"x" * 32


def _make_config(*args: str) -> PicoptSettings:
    return PicoptConfig().get_config(cli.get_arguments(("picopt", *args, ".")))


def _make_skipper(*args: str) -> WalkSkipper:
    return WalkSkipper(_make_config(*args), Reporter())


class TestWalkSkipper:
    """Skip rule unit tests."""

    def test_timestamps_file_skipped_by_basename(self: Any, tmp_path: Path) -> None:
        """Treestamps yaml files are skipped even when named by full path."""
        skipper = _make_skipper()
        fname = next(iter(Treestamps.get_filenames(PROGRAM_NAME)))
        stamp_path = tmp_path / fname
        stamp_path.write_bytes(_DATA)
        path_info = PathInfo(top_path=tmp_path, path=stamp_path, convert=False)
        assert skipper.is_walk_file_skip(path_info)

    def test_ignore_respects_case_sensitivity(self: Any, tmp_path: Path) -> None:
        """Uppercase ignore patterns don't match lowercase files on case-sensitive filesystems."""
        skipper = _make_skipper("-i", "*.BAK")
        path = tmp_path / "keep.bak"
        path.write_bytes(_DATA)
        sensitive = PathInfo(
            top_path=tmp_path, path=path, convert=False, is_case_sensitive=True
        )
        assert not skipper.is_walk_file_skip(sensitive)
        insensitive = PathInfo(
            top_path=tmp_path, path=path, convert=False, is_case_sensitive=False
        )
        assert skipper.is_walk_file_skip(insensitive)

    @pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="platform lacks mkfifo")
    def test_fifo_skipped_without_blocking(self: Any, tmp_path: Path) -> None:
        """Named pipes are skipped instead of blocking the walk forever."""
        skipper = _make_skipper()
        fifo_path = tmp_path / "pipe.png"
        os.mkfifo(fifo_path)
        path_info = PathInfo(top_path=tmp_path, path=fifo_path, convert=False)
        assert skipper.is_walk_file_skip(path_info)


class _FakeNodeHandler:
    """Container handler stand-in collecting noop members."""

    def __init__(self) -> None:
        self._optimized_contents: set[Any] = set()

    def get_optimized_contents(self) -> set[Any]:
        return self._optimized_contents


class TestEnqueueChildrenResilience:
    """A member that explodes during detection is one error, not a run-ender."""

    def test_detection_error_keeps_member_and_continues(
        self: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The failed member is passed through; later members still process."""
        walk = Walk(_make_config())
        try:

            def _bomb(_path_info: PathInfo) -> None:
                msg = "simulated DecompressionBombError"
                raise ValueError(msg)

            monkeypatch.setattr(walk, "_create_handler", _bomb)
            handler = _FakeNodeHandler()
            node = ContainerNode(handler=handler)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            children = [
                PathInfo(
                    top_path=Path(),
                    path=None,
                    convert=False,
                    is_case_sensitive=True,
                    data=_DATA,
                )
                for _ in range(2)
            ]
            walk._enqueue_children(None, node, children)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            assert handler.get_optimized_contents() == set(children)
        finally:
            walk._executor.shutdown(wait=False)


class TestWalkResilience:
    """Hostile directory trees must not crash or hang the walk."""

    def test_symlink_directory_loop_terminates_cleanly(
        self: Any, tmp_path: Path
    ) -> None:
        """A symlink cycle is walked once, with no errors."""
        from picopt import PROGRAM_NAME, cli
        from tests import IMAGES_DIR

        subdir = tmp_path / "sub"
        subdir.mkdir()
        (subdir / "loop").symlink_to(tmp_path, target_is_directory=True)
        png = subdir / "test_png.png"
        png.write_bytes((IMAGES_DIR / "test_png.png").read_bytes())
        orig_size = png.stat().st_size

        cli.main((PROGRAM_NAME, "-rvx", "PNG", str(tmp_path)))

        assert png.stat().st_size < orig_size

    def test_unreadable_dir_does_not_crash_legacy_import(
        self: Any, tmp_path: Path
    ) -> None:
        """Legacy timestamp import skips unreadable directories."""
        from picopt import PROGRAM_NAME, cli

        (tmp_path / ".picopt_timestamp").touch()
        locked = tmp_path / "locked"
        locked.mkdir()
        locked.chmod(0o000)
        try:
            cli.main((PROGRAM_NAME, "-rtv", str(tmp_path)))
        finally:
            locked.chmod(0o755)
