"""Test comic format."""
from pathlib import Path
from unittest import TestCase

from picopt.formats.comic import Comic

TEST_FILES_ROOT = 'tests/test_files'
COMIC_ROOT = TEST_FILES_ROOT+'/comic_archives'


class TestGetComicFormat(TestCase):

    def test_cbz(self) -> None:
        res = Comic.get_comic_format(Path(COMIC_ROOT+'/test_cbz.cbz'))
        self.assertEqual(res, 'CBZ')

    def test_cbr(self) -> None:
        res = Comic.get_comic_format(Path(COMIC_ROOT+'/test_cbr.cbr'))
        self.assertEqual(res, 'CBR')

    def test_dir(self) -> None:
        res = Comic.get_comic_format(Path(COMIC_ROOT))
        self.assertIsNone(res)


class TestGetArchiveTmpDir(TestCase):

    def test_foo(self) -> None:
        res = Comic._get_archive_tmp_dir(Path('foo'))
        self.assertEqual(str(res), 'picopt_tmp_foo')
