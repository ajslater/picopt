"""Test handling files module."""
import shutil

from pathlib import Path
from typing import Tuple

from confuse.templates import AttrDict

from picopt import files
from picopt.handlers.png import Png
from tests import get_test_dir


__all__ = ()  # hides module from pydocstring
TMP_DIR = get_test_dir()
TEST_FILE_OLD = TMP_DIR / "test"
TEST_FILE_NEW = TMP_DIR / "test-NEW"
_BMP_FORMAT = "BMP"


def _fmt_to_suffix(fmt: str) -> str:
    return "." + fmt.lower()


def _create_file(path: Path, fmt: str, num_chars: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = _fmt_to_suffix(fmt)
    path = path.with_suffix(suffix)
    path.write_text("x" * num_chars)
    return path


def _teardown() -> None:
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)


def _cleanup_aux(
    old_size: int,
    new_size: int,
    old_format: str,
    new_format: str,
    config: AttrDict,
    cause_error: bool = False,
) -> Tuple[Tuple[Path, int, int], Path, Path]:
    if cause_error:
        old_path = TMP_DIR / "old"
        new_path = TMP_DIR / "new"
    else:
        old_path = _create_file(TEST_FILE_OLD, old_format, old_size)
        new_path = _create_file(TEST_FILE_NEW, new_format, new_size)
    final_suffix = _fmt_to_suffix(new_format)
    res = files._cleanup_after_optimize_aux(config, old_path, new_path, final_suffix)
    assert not new_path.exists()
    if old_format != new_format:
        new_path = old_path.with_suffix(_fmt_to_suffix(new_format))
    else:
        new_path = old_path
    return res, old_path, new_path


def test_small_big() -> None:
    old_size = 32
    new_size = 40
    old_format = Png.FORMAT_STR
    new_format = Png.FORMAT_STR
    config = AttrDict(test=False, bigger=True)
    (_, b_in, b_out), old_path, new_path = _cleanup_aux(
        old_size, new_size, old_format, new_format, config
    )
    assert old_path.is_file()
    assert old_size == b_in
    assert new_size == b_out
    assert new_path.stat().st_size == new_size
    _teardown()


def test_big_small() -> None:
    old_size = 44
    new_size = 4
    old_format = _BMP_FORMAT
    new_format = Png.FORMAT_STR
    config = AttrDict(test=False, bigger=False)
    (path, b_in, b_out), old_path, new_path = _cleanup_aux(
        old_size, new_size, old_format, new_format, config
    )
    assert new_path.is_file()
    assert not old_path.exists()
    assert new_path == old_path.with_suffix(_fmt_to_suffix(new_format))
    assert old_size == b_in
    assert new_size == b_out
    _teardown()


def test_small_small() -> None:
    old_size = 5
    new_size = 5
    old_format = _BMP_FORMAT
    new_format = Png.FORMAT_STR
    config = AttrDict(test=False, bigger=False)
    (path, b_in, b_out), old_path, new_path = _cleanup_aux(
        old_size, new_size, old_format, new_format, config
    )
    assert not new_path.is_file()
    assert old_path.exists()
    assert new_path == old_path.with_suffix(_fmt_to_suffix(new_format))
    assert old_size == b_in
    assert old_size == b_out
    _teardown()


def test_small_big_format_change_bigger() -> None:
    old_size = 5
    new_size = 50
    old_format = _BMP_FORMAT
    new_format = Png.FORMAT_STR
    config = AttrDict(test=False, bigger=True)
    (path, b_in, b_out), old_path, new_path = _cleanup_aux(
        old_size, new_size, old_format, new_format, config
    )
    assert new_path.is_file()
    assert not old_path.exists()
    assert new_path == old_path.with_suffix(_fmt_to_suffix(new_format))
    assert old_size == b_in
    assert new_size == b_out
    _teardown()


def test_small_big_bigger() -> None:
    old_size = 5
    new_size = 50
    old_format = Png.FORMAT_STR
    new_format = Png.FORMAT_STR
    config = AttrDict(test=False, bigger=True)
    (path, b_in, b_out), old_path, new_path = _cleanup_aux(
        old_size, new_size, old_format, new_format, config
    )
    assert old_path.is_file()
    assert new_path == old_path
    assert old_size == b_in
    assert new_size == b_out
    assert new_size == old_path.stat().st_size
    _teardown()


def test_os_error() -> None:
    old_size = 5
    new_size = 50
    old_format = Png.FORMAT_STR
    new_format = Png.FORMAT_STR
    config = AttrDict(test=True, bigger=True)
    (path, b_in, b_out), old_path, new_path = _cleanup_aux(
        old_size, new_size, old_format, new_format, config, True
    )
    assert path.suffix == ""
    assert 0 == b_in
    assert 0 == b_out
    _teardown()


def test_cleanup_after_optimize() -> None:
    old_size = 32
    new_size = 5
    old_format = _BMP_FORMAT
    new_format = Png.FORMAT_STR
    old_path = _create_file(TEST_FILE_OLD, old_format, old_size)
    new_path = _create_file(TEST_FILE_OLD, new_format, new_size)
    final_suffix = "." + new_format.lower()
    config = AttrDict(test=False, bigger=False)
    res = files.cleanup_after_optimize(config, old_path, new_path, final_suffix)
    new_suffix = _fmt_to_suffix(new_format)
    final_new_path = TEST_FILE_OLD.with_suffix(new_suffix)
    assert res.final_path == final_new_path
    assert res.bytes_in == old_size
    assert res.bytes_out == new_size
    _teardown()
