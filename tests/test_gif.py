"""Test gif module."""
import shutil

from picopt.extern import ExtArgs
from picopt.formats import gif
from tests import IMAGES_DIR
from tests import get_test_dir


__all__ = ()  # hides module from pydocstring
TEST_GIF_SRC = IMAGES_DIR / "test_gif.gif"
TMP_ROOT = get_test_dir()
OLD_PATH = TMP_ROOT / "old.gif"


def _setup():
    print(TMP_ROOT)
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
