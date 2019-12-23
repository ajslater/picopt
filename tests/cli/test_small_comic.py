"""Test comic format."""
import shutil
from pathlib import Path
from unittest import TestCase

from picopt import cli

TEST_FILES_SRC: str = 'tests/test_files'
TEST_FILES_DST_ROOT: str = '/tmp'
TEST_FILES_DST: Path = Path(TEST_FILES_DST_ROOT).joinpath('picopt_tests')
TEST_SMALL_COMIC: Path = Path(TEST_FILES_DST).joinpath(
                                'comic_archives/test_small_cbz.cbz')


class TestCLI(TestCase):

    def setUp(self) -> None:
        if TEST_FILES_DST.exists():
            shutil.rmtree(TEST_FILES_DST)
        shutil.copytree(TEST_FILES_SRC, TEST_FILES_DST)

    def tearDown(self) -> None:
        shutil.rmtree(TEST_FILES_DST)


class TestCLISmallComic(TestCLI):

    def test_small_comic(self) -> None:
        args = ('', '-rct', str(TEST_SMALL_COMIC))
        res = cli.run(args)
        self.assertTrue(res)
