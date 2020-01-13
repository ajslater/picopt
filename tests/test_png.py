"""Test png module."""
import shutil

from pathlib import Path

from picopt.extern import ExtArgs
from picopt.formats.png import Png


__all__ = ()  # hides module from pydocstring
TEST_FILES_ROOT = Path("tests/test_files")
IMAGES_ROOT = TEST_FILES_ROOT / "images"
TMP_DIR = Path("/tmp/picopt-test_png")
TMP_OLD_PATH = TMP_DIR / "old.png"
TEST_SRC_PATH = IMAGES_ROOT / "test_png.png"
TEST_SRC_PATH_16 = IMAGES_ROOT / "test_png_16rgba.png"


def _setup(use_16=False):
    if use_16:
        src_path = TEST_SRC_PATH_16
    else:
        src_path = TEST_SRC_PATH
    TMP_DIR.mkdir(exist_ok=True)
    shutil.copy(src_path, TMP_OLD_PATH)
    args = ExtArgs(str(TMP_OLD_PATH), str(TMP_OLD_PATH))
    return args


def _teardown(args):
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)


def test_optipng():
    args = _setup()
    res = Png.optipng(None, args)
    assert res == "PNG"
    _teardown(args)


# def test_advpng():
#    args = _setup()
#    res = Png.advpng(None, args)
#    assert res == "PNG"
#    _teardown(args)


def test_pngout():
    args = _setup()
    res = Png.pngout(None, args)
    assert res == "PNG"
    _teardown(args)


def test_pngout_16():
    args = _setup(True)
    res = Png.pngout(None, args)
    assert res == "PNG"
    _teardown(args)
