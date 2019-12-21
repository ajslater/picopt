"""Test comic format."""
from unittest import TestCase

from picopt.formats import comic
from pathlib import Path

TEST_FILES_ROOT = 'tests/test_files'
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
        res = comic._get_archive_tmp_dir(Path('foo'))
        self.assertEqual(str(res), 'picopt_tmp_foo')
