"""Test comic format."""
import os
import glob
import shutil
from unittest import TestCase

from picopt import cli

TEST_FILES_SRC = 'tests/test_files'
TEST_FILES_DST_ROOT = '/tmp'
TEST_FILES_DST = os.path.join(TEST_FILES_DST_ROOT, 'picopt_tests')


class TestCLI(TestCase):

    def setUp(self):
        if os.path.exists(TEST_FILES_DST):
            shutil.rmtree(TEST_FILES_DST)
        shutil.copytree(TEST_FILES_SRC, TEST_FILES_DST)

    def tearDown(self):
        shutil.rmtree(TEST_FILES_DST)


class TestCLIImages(TestCLI):

    def test_walk_images(self):
        args = [None] + glob.glob(TEST_FILES_DST+'/*')
        cli.run(args)


class TestCLIEverything(TestCLI):

    def test_all_once(self):
        args = [None, '-rct', TEST_FILES_DST]
        cli.run(args)
