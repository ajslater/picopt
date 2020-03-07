"""Test comic format."""
import shutil

from picopt import cli
from tests import IMAGES_DIR
from tests import get_test_dir


__all__ = ()
TMP_ROOT = get_test_dir()


def setup() -> None:
    teardown()
    shutil.copytree(IMAGES_DIR, TMP_ROOT)


def teardown() -> None:
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)


def test_walk_images() -> None:
    setup()
    args = tuple("") + tuple(map(str, TMP_ROOT.glob("*")))
    res = cli.run(args)
    assert res
    teardown()


def test_all_once() -> None:
    setup()
    args = ("", "-rct", str(TMP_ROOT))
    res = cli.run(args)
    assert res
    teardown()
