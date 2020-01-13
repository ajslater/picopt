"""Test gif module."""
import shutil

from pathlib import Path

from picopt.extern import ExtArgs
from picopt.formats import gif


__all__ = ()  # hides module from pydocstring
TEST_FILES_ROOT = Path("tests/test_files/")
IMAGES_ROOT = TEST_FILES_ROOT / "images"
TEST_GIF_SRC = IMAGES_ROOT / "test_gif.gif"
TMP_ROOT = Path("/tmp/picopt-test_gif")
OLD_PATH = TMP_ROOT / "old.gif"


def _setup():
    TMP_ROOT.mkdir(exist_ok=True)


def _teardown():
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)


def test_gifiscle():
    _setup()
    shutil.copy(TEST_GIF_SRC, OLD_PATH)
    args = ExtArgs("", str(OLD_PATH))
    res = gif.Gif.gifsicle(None, args)
    assert res == "GIF"
    _teardown()
