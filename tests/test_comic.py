"""Test comic format."""
from unittest import TestCase

from picopt import comic

TEST_FILES_ROOT = 'old_tests/test_files'
COMIC_ROOT = TEST_FILES_ROOT+'/comic_archives'


class TestGetComicFormat(TestCase):

    def test_cbz(self):
        res = comic.get_comic_format(COMIC_ROOT+'/test_cbz.cbz')
        self.assertEqual(res, 'CBZ')

    def test_cbr(self):
        res = comic.get_comic_format(COMIC_ROOT+'/test_cbr.cbr')
        self.assertEqual(res, 'CBR')

    def test_dir(self):
        res = comic.get_comic_format(COMIC_ROOT)
        self.assertEqual(res, None)

class TestGetArchiveTmpDir(TestCase):

    def test_foo(self):
        res = comic.get_archive_tmp_dir('foo')
        self.assertEqual(res, 'picopt_tmp_foo')
