"""Test gif module."""
import shutil

from pathlib import Path

from picopt.extern import ExtArgs
from picopt.formats import gif


__all__ = ()  # hides module from pydocstring
TEST_FILES_ROOT = Path("tests/test_files/")
IMAGES_ROOT = TEST_FILES_ROOT / "images"
TEST_GIF_SRC = IMAGES_ROOT / "test_gif.gif"
TMP_ROOT = Path("/tmp")
OLD_PATH = TMP_ROOT / "old.gif"


def test_gifiscle():
    shutil.copy(TEST_GIF_SRC, OLD_PATH)
    args = ExtArgs("", str(OLD_PATH))
    res = gif.Gif.gifsicle(None, args)
    assert res == "GIF"
    OLD_PATH.unlink()