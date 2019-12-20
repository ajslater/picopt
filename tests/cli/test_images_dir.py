"""Test comic format."""
import shutil
from pathlib import Path
from unittest import TestCase

from picopt import cli

TEST_FILES_SRC = 'tests/test_files'
TEST_FILES_DST = Path('/tmp').joinpath('picopt_tests')


class TestCLI(TestCase):

    def setUp(self):
        if TEST_FILES_DST.exists():
            shutil.rmtree(TEST_FILES_DST)
        shutil.copytree(TEST_FILES_SRC, TEST_FILES_DST)

    def tearDown(self):
        shutil.rmtree(TEST_FILES_DST)


class TestCLIImages(TestCLI):

    def test_walk_images(self):
        args = [None] + list(map(str, TEST_FILES_DST.glob('*')))
        res = cli.run(args)
        self.assertTrue(res)


class TestCLIEverything(TestCLI):

    def test_all_once(self):
        args = [None, '-rct', str(TEST_FILES_DST)]
        res = cli.run(args)
        self.assertTrue(res)
