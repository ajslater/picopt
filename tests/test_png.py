"""Test png module."""
import shutil

from pathlib import Path

from picopt.extern import ExtArgs
from picopt.formats.png import Png


__all__ = ()  # hides module from pydocstring
TEST_FILES_ROOT = Path("tests/test_files")
IMAGES_ROOT = TEST_FILES_ROOT / "images"
TMP_DIR = Path("/tmp")
TMP_OLD_PATH = TMP_DIR / "old.png"
TEST_SRC_PATH = IMAGES_ROOT / "test_png.png"
TEST_SRC_PATH_16 = IMAGES_ROOT / "test_png_16rgba.png"


def _setup_png(use_16=False):
    if use_16:
        src_path = TEST_SRC_PATH_16
    else:
        src_path = TEST_SRC_PATH
    shutil.copy(src_path, TMP_OLD_PATH)
    args = ExtArgs(str(TMP_OLD_PATH), str(TMP_OLD_PATH))
    return args


def _teardown_png(args):
    Path(args.new_fn).unlink()


def test_optipng():
    args = _setup_png()
    res = Png.optipng(None, args)
    assert res == "PNG"
    _teardown_png(args)


# def test_advpng():
#    args = _setup_png()
#    res = Png.advpng(None, args)
#    assert res == "PNG"
#    _teardown_png(args)


def test_pngout():
    args = _setup_png()
    res = Png.pngout(None, args)
    assert res == "PNG"
    _teardown_png(args)


def test_pngout_16():
    args = _setup_png(True)
    res = Png.pngout(None, args)
    assert res == "PNG"
    _teardown_png(args)
