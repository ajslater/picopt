"""Test gif module."""
import shutil

from picopt.extern import ExtArgs
from picopt.formats import gif
from picopt.settings import Settings
from tests import IMAGES_DIR
from tests import get_test_dir


__all__ = ()  # hides module from pydocstring
TEST_GIF_SRC = IMAGES_DIR / "test_gif.gif"
TMP_ROOT = get_test_dir()
OLD_PATH = TMP_ROOT / "old.gif"


def _setup() -> None:
    print(TMP_ROOT)
    TMP_ROOT.mkdir(exist_ok=True)


def _teardown() -> None:
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)


def test_gifiscle() -> None:
    _setup()
    shutil.copy(TEST_GIF_SRC, OLD_PATH)
    args = ExtArgs("", str(OLD_PATH))
    res = gif.Gif.gifsicle(Settings(), args)
    assert res == "GIF"
    _teardown()
