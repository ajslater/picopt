"""Test the replace/discard policy of Handler._cleanup_after_optimize."""

import os
from io import BytesIO
from pathlib import Path
from subprocess import CalledProcessError
from typing import BinaryIO

import pytest
from typing_extensions import override

from picopt import WORKING_SUFFIX
from picopt.config.settings import ComputedSettings, IgnorePatterns, PicoptSettings
from picopt.path import PathInfo
from picopt.plugins.base.format import FileFormat
from picopt.plugins.base.handler import Handler

__all__ = ()

_ORIGINAL_DATA = b"original image data" * 64
_OPTIMIZED_DATA = b"optimized"

_PNG_FORMAT = FileFormat("PNG", lossless=True, animated=False)


class _StubHandler(Handler):
    """Concrete Handler; optimize() is bypassed in these tests."""

    OUTPUT_FORMAT_STR = "PNG"
    OUTPUT_FILE_FORMAT = _PNG_FORMAT
    SUFFIXES = (".png",)

    @override
    def optimize(self) -> BinaryIO:
        """Unused; tests call _cleanup_after_optimize directly."""
        raise NotImplementedError


class _StubConvertHandler(_StubHandler):
    """Converting handler: .png input becomes a .webp final path."""

    OUTPUT_FORMAT_STR = "WEBP"
    OUTPUT_FILE_FORMAT = FileFormat("WEBP", lossless=True, animated=False)
    SUFFIXES = (".webp",)


def _make_settings(*, dry_run: bool = False, preserve: bool = False) -> PicoptSettings:
    computed = ComputedSettings(
        handler_stages={}, ignore=IgnorePatterns(case=None, ignore_case=None)
    )
    return PicoptSettings(
        bigger=False,
        dry_run=dry_run,
        fail_fast=False,
        fail_fast_container=False,
        ignore_defaults=True,
        jobs=1,
        keep_metadata=True,
        list_only=False,
        memory_limit=0,
        near_lossless=False,
        png_max=False,
        preserve=preserve,
        recurse=True,
        symlinks=True,
        timestamps=False,
        timestamps_check_config=True,
        timestamps_ignore_archive_entry_mtimes=False,
        verbose=0,
        disable_programs=(),
        formats=(),
        ignore=(),
        paths=(),
        after=None,
        convert_to=None,
        extra_formats=None,
        computed=computed,
    )


def _make_handler(
    tmp_path: Path,
    handler_cls: type[_StubHandler] = _StubHandler,
    *,
    dry_run: bool = False,
    preserve: bool = False,
) -> tuple[_StubHandler, Path]:
    original_path = tmp_path / "test.png"
    original_path.write_bytes(_ORIGINAL_DATA)
    path_info = PathInfo(top_path=tmp_path, path=original_path, convert=False)
    handler = handler_cls(
        _make_settings(dry_run=dry_run, preserve=preserve), path_info, _PNG_FORMAT
    )
    return handler, original_path


def test_replace_success_is_atomic_and_clean(tmp_path: Path) -> None:
    """A smaller result replaces the original and leaves no temp files."""
    handler, original_path = _make_handler(tmp_path)
    report = handler._cleanup_after_optimize(BytesIO(_OPTIMIZED_DATA))
    assert report.exc is None
    assert original_path.read_bytes() == _OPTIMIZED_DATA
    assert not list(tmp_path.glob(f"*{WORKING_SUFFIX}*"))


def test_crash_during_replace_preserves_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crash at the final rename must leave the original file intact."""
    handler, original_path = _make_handler(tmp_path)

    def _crash(self: Path, _target: Path) -> Path:
        msg = f"simulated crash replacing {self}"
        raise OSError(msg)

    monkeypatch.setattr(Path, "replace", _crash)
    with pytest.raises(OSError, match="simulated crash"):
        handler._cleanup_after_optimize(BytesIO(_OPTIMIZED_DATA))
    assert original_path.read_bytes() == _ORIGINAL_DATA


def test_write_failure_preserves_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure while writing new data (e.g. ENOSPC) must not touch the original."""
    handler, original_path = _make_handler(tmp_path)
    real_open = Path.open

    def _no_space(self: Path, mode: str = "r", *args, **kwargs) -> object:
        if "w" in mode:
            msg = f"simulated disk full writing {self}"
            raise OSError(msg)
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _no_space)
    with pytest.raises(OSError, match="simulated disk full"):
        handler._cleanup_after_optimize(BytesIO(_OPTIMIZED_DATA))
    assert original_path.read_bytes() == _ORIGINAL_DATA


def test_discarded_bigger_conversion_is_a_skip_not_an_error(tmp_path: Path) -> None:
    """A conversion result bigger than the input is discarded quietly."""
    handler, original_path = _make_handler(tmp_path, _StubConvertHandler)
    bigger_data = _ORIGINAL_DATA + b"bloat"
    report = handler._cleanup_after_optimize(BytesIO(bigger_data))
    assert report.exc is None
    assert not report.converted
    assert not report.changed
    assert report.path == original_path
    assert original_path.read_bytes() == _ORIGINAL_DATA
    assert not (tmp_path / "test.webp").exists()
    # path_info must still point at the file that actually exists
    assert handler.path_info.path == original_path


def test_dry_run_conversion_writes_nothing(tmp_path: Path) -> None:
    """Dry-run reports the would-be result without touching the filesystem."""
    handler, original_path = _make_handler(tmp_path, _StubConvertHandler, dry_run=True)
    report = handler._cleanup_after_optimize(BytesIO(_OPTIMIZED_DATA))
    assert report.exc is None
    assert not report.converted
    assert not report.changed
    assert original_path.read_bytes() == _ORIGINAL_DATA
    assert not (tmp_path / "test.webp").exists()
    assert not list(tmp_path.glob(f"*{WORKING_SUFFIX}*"))


def test_preserve_survives_chown_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--preserve still restores mode and mtime when chown is denied."""
    handler, original_path = _make_handler(tmp_path, preserve=True)
    original_mtime_ns = original_path.stat().st_mtime_ns

    def _denied(*_args, **_kwargs) -> None:
        msg = "Operation not permitted"
        raise PermissionError(msg)

    monkeypatch.setattr(os, "chown", _denied)
    report = handler._cleanup_after_optimize(BytesIO(_OPTIMIZED_DATA))
    assert report.exc is None
    assert original_path.read_bytes() == _OPTIMIZED_DATA
    assert original_path.stat().st_mtime_ns == original_mtime_ns


def test_run_ext_fs_cleans_temp_input_when_tool_fails(tmp_path: Path) -> None:
    """A failed external tool must not leave the spilled temp input behind."""
    handler, _ = _make_handler(tmp_path)
    input_path = tmp_path / "spilled.tmp"
    with pytest.raises(CalledProcessError):
        handler.run_ext_fs(
            ("/usr/bin/false",),
            BytesIO(_ORIGINAL_DATA),
            input_path,
            input_path_tmp=True,
        )
    assert not input_path.exists()
