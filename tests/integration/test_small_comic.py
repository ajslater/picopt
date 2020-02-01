"""Test comic format."""
import shutil

from picopt import cli
from tests import COMIC_DIR
from tests import get_test_dir


__all__ = ()
TMP_ROOT = get_test_dir()
SRC_CBZ = COMIC_DIR / "test_cbz.cbz"


def setup() -> None:
    teardown()
    TMP_ROOT.mkdir()


def teardown() -> None:
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)


def test_small_comic() -> None:
    setup()
    path = TMP_ROOT / "test.cbz"
    shutil.copy(SRC_CBZ, path)
    args = ("", "-rct", str(path))
    res = cli.run(args)
    assert res
    teardown()
