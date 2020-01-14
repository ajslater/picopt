"""Test jpeg module."""
import shutil

from pathlib import Path

from picopt.extern import ExtArgs
from picopt.formats import jpeg
from picopt.settings import Settings
from tests import IMAGES_DIR
from tests import get_test_dir


__all__ = ()  # hides module from pydocstring
TMP_ROOT = get_test_dir()
JPEG_SRC = IMAGES_DIR / "test_jpg.jpg"
TEST_OLD_JPEG = TMP_ROOT / "old.jpeg"
TEST_NEW_JPEG = TMP_ROOT / "new.jpeg"


def _setup_jpeg():
    TMP_ROOT.mkdir(exist_ok=True)
    shutil.copy(JPEG_SRC, TEST_OLD_JPEG)
    args = ExtArgs(str(TEST_OLD_JPEG), str(TEST_NEW_JPEG))
    return args, Settings()


def _teardown(args):
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)


def test_mozjpeg():
    args, settings = _setup_jpeg()
    res = jpeg.Jpeg.mozjpeg(settings, args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown(args)


def test_mozjpeg_destroy_metadata():
    args, settings = _setup_jpeg()
    settings.destroy_metadata = True
    res = jpeg.Jpeg.mozjpeg(settings, args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown(args)


def test_jpegtran():
    args, settings = _setup_jpeg()
    res = jpeg.Jpeg.jpegtran(settings, args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown(args)


def test_jpegtran_options():
    args, settings = _setup_jpeg()
    settings.destroy_metadata = True
    settings.jpegtran_prog = False
    res = jpeg.Jpeg.jpegtran(settings, args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown(args)


def test_jpegrescan():
    args, settings = _setup_jpeg()
    res = jpeg.Jpeg.jpegrescan(settings, args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown(args)


def test_jpegrescan_options():
    args, settings = _setup_jpeg()
    settings.destroy_metadata = True
    settings.jpegrescan_multithread = False
    res = jpeg.Jpeg.jpegrescan(settings, args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown(args)
