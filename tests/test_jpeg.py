"""Test jpeg module."""
import shutil

from pathlib import Path

from picopt.extern import ExtArgs
from picopt.formats import jpeg
from picopt.settings import Settings


__all__ = ()  # hides module from pydocstring
TEST_FILES_ROOT = "tests/test_files/"
IMAGES_ROOT = TEST_FILES_ROOT + "/images"
SETTINGS = Settings()


def _setup_jpeg():
    old_path = Path("/tmp/old.jpeg")
    new_path = Path("/tmp/new.jpeg")
    test_fn_src = Path(IMAGES_ROOT + "/test_jpg.jpg")
    shutil.copy(test_fn_src, old_path)
    args = ExtArgs(str(old_path), str(new_path))
    return args


def _rm(fn):
    path = Path(fn)
    if path.exists:
        path.unlink()


def _teardown_jpeg(args):
    _rm(args.old_fn)
    _rm(args.new_fn)


def test_mozjpeg():
    args = _setup_jpeg()
    res = jpeg.Jpeg.mozjpeg(SETTINGS, args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown_jpeg(args)


def test_mozjpeg_destroy_metadata():
    args = _setup_jpeg()
    settings = Settings()
    settings.destroy_metadata = True
    res = jpeg.Jpeg.mozjpeg(settings, args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown_jpeg(args)


def test_jpegtran():
    args = _setup_jpeg()
    res = jpeg.Jpeg.jpegtran(SETTINGS, args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown_jpeg(args)


def test_jpegtran_options():
    args = _setup_jpeg()
    settings = Settings()
    settings.destroy_metadata = True
    settings.jpegtran_prog = False
    res = jpeg.Jpeg.jpegtran(settings, args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown_jpeg(args)


def test_jpegrescan():
    args = _setup_jpeg()
    res = jpeg.Jpeg.jpegrescan(SETTINGS, args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown_jpeg(args)


def test_jpegrescan_options():
    args = _setup_jpeg()
    settings = Settings()
    settings.destroy_metadata = True
    settings.jpegrescan_multithread = False
    res = jpeg.Jpeg.jpegrescan(settings, args)
    assert res == "JPEG"
    assert Path(args.new_fn).is_file()
    _teardown_jpeg(args)
