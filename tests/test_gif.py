"""Test gif module."""
import shutil

from pathlib import Path

from picopt.extern import ExtArgs
from picopt.formats import gif


__all__ = ()  # hides module from pydocstring
TEST_FILES_ROOT = "tests/test_files/"
IMAGES_ROOT = TEST_FILES_ROOT + "/images"


def test_gifiscle():
    old_path = Path("/tmp/old.gif")
    test_fn_src = Path(IMAGES_ROOT + "/test_gif.gif")
    shutil.copy(test_fn_src, old_path)
    args = ExtArgs("", str(old_path))
    res = gif.Gif.gifsicle(None, args)
    assert res == "GIF"
    old_path.unlink()
