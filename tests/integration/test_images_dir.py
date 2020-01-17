"""Test comic format."""
import shutil

from unittest import TestCase

from picopt import cli
from tests import IMAGES_DIR
from tests import get_test_dir


__all__ = ()
TMP_ROOT = get_test_dir()


class TestCLI(TestCase):
    def setUp(self) -> None:
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)
        shutil.copytree(IMAGES_DIR, TMP_ROOT)

    def tearDown(self) -> None:
        shutil.rmtree(TMP_ROOT)


class TestCLIImages(TestCLI):
    def test_walk_images(self) -> None:
        args = tuple("") + tuple(map(str, TMP_ROOT.glob("*")))
        res = cli.run(args)
        assert res


class TestCLIEverything(TestCLI):
    def test_all_once(self) -> None:
        args = ("", "-rct", str(TMP_ROOT))
        res = cli.run(args)
        assert res
