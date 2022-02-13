"""Test jpeg module."""
import shutil

from pathlib import Path

from picopt.extern import ExtArgs
from picopt.formats.jpeg import JPEG_FORMAT, Jpeg
from tests import IMAGES_DIR, get_test_dir


__all__ = ()  # hides module from pydocstring
TMP_ROOT = get_test_dir()
JPEG_SRC = IMAGES_DIR / "test_jpg.jpg"
TEST_OLD_JPEG = TMP_ROOT / "old.jpeg"
TEST_NEW_JPEG = TMP_ROOT / "new.jpeg"


def _setup_jpeg(destroy_metadata=False) -> ExtArgs:
    TMP_ROOT.mkdir(exist_ok=True)
    shutil.copy(JPEG_SRC, TEST_OLD_JPEG)
    args = ExtArgs(
        str(TEST_OLD_JPEG), str(TEST_NEW_JPEG), JPEG_FORMAT, destroy_metadata
    )
    return args


def _teardown(_: ExtArgs) -> None:
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)


def test_mozjpeg() -> None:
    args = _setup_jpeg()
    res = Jpeg.mozjpeg(args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown(args)


def test_mozjpeg_destroy_metadata() -> None:
    args = _setup_jpeg(True)
    res = Jpeg.mozjpeg(args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown(args)


def test_jpegtran() -> None:
    args = _setup_jpeg()
    res = Jpeg.jpegtran(args)
    args = _setup_jpeg()
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown(args)


def test_jpegtran_options() -> None:
    args = _setup_jpeg(True)
    res = Jpeg.jpegtran(args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown(args)
