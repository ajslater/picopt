"""Test comic format."""
import shutil

from unittest import TestCase

from picopt import cli
from tests import COMIC_DIR
from tests import get_test_dir


__all__ = ()
TMP_ROOT = get_test_dir()
SRC_CBZ = COMIC_DIR / "test_cbz.cbz"


class TestCLI(TestCase):
    def setUp(self) -> None:
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)
        TMP_ROOT.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(TMP_ROOT)


class TestCLISmallComic(TestCLI):
    def test_small_comic(self) -> None:
        path = TMP_ROOT / "test.cbz"
        shutil.copy(SRC_CBZ, path)
        args = ("", "-rct", str(path))
        res = cli.run(args)
        assert res
