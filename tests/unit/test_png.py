"""Test png module."""
import shutil

from picopt.extern import ExtArgs
from picopt.handlers.png import Png
from tests import IMAGES_DIR, get_test_dir


__all__ = ()  # hides module from pydocstring
TMP_DIR = get_test_dir()
TMP_OLD_PATH = TMP_DIR / "old.png"
TEST_SRC_PATH = IMAGES_DIR / "test_png.png"
TEST_SRC_PATH_16 = IMAGES_DIR / "test_png_16rgba.png"


def _setup(use_16: bool = False) -> ExtArgs:
    if use_16:
        src_path = TEST_SRC_PATH_16
    else:
        src_path = TEST_SRC_PATH
    TMP_DIR.mkdir(exist_ok=True)
    shutil.copy(src_path, TMP_OLD_PATH)
    args = ExtArgs(str(TMP_OLD_PATH), str(TMP_OLD_PATH), False)
    return args


def _teardown(_: ExtArgs) -> None:
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)


def test_optipng() -> None:
    args = _setup()
    res = Png.optipng(args)
    assert res == Png.SUFFIX
    _teardown(args)


def test_pngout() -> None:
    args = _setup()
    res = Png.pngout(args)
    assert res == Png.SUFFIX
    _teardown(args)


def test_pngout_16() -> None:
    args = _setup(True)
    res = Png.pngout(args)
    assert res == Png.SUFFIX
    _teardown(args)
