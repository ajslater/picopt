"""Test comic format."""
import os
import shutil
from unittest import TestCase

from picopt import cli

TEST_FILES_SRC = 'tests/test_files'
TEST_FILES_DST_ROOT = '/tmp'
TEST_FILES_DST = os.path.join(TEST_FILES_DST_ROOT, 'picopt_tests')
TEST_SMALL_COMIC = os.path.join(TEST_FILES_DST,
                                'comic_archives/test_small_cbz.cbz')


class TestCLI(TestCase):

    def setUp(self):
        if os.path.exists(TEST_FILES_DST):
            shutil.rmtree(TEST_FILES_DST)
        shutil.copytree(TEST_FILES_SRC, TEST_FILES_DST)

    def tearDown(self):
        shutil.rmtree(TEST_FILES_DST)


class TestCLISmallComic(TestCLI):

    def test_small_comic(self):
        args = [None, '-rct', TEST_SMALL_COMIC]
        cli.run(args)
