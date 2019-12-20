"""Test comic format."""
from unittest import TestCase
from pathlib import Path

from picopt import timestamp
from picopt.settings import Settings

TEST_FILES_ROOT = 'tests/test_files'
COMIC_ROOT = TEST_FILES_ROOT+'/comic_archives'


def _get_timestamp_setup():
    record_path = Path(TEST_FILES_ROOT).joinpath(timestamp.RECORD_FILENAME)
    record_path.touch()
    return record_path, record_path.stat().st_mtime


class TestTimestamp(TestCase):

    def test_get_timestamp_ne(self):
        path = Path(TEST_FILES_ROOT).joinpath('BLARGH')
        res = timestamp._get_timestamp(path, False)
        self.assertEqual(res, None)

    def test_get_timestamp_no_remove(self):
        record_filename, mtime = _get_timestamp_setup()
        res = timestamp._get_timestamp(TEST_FILES_ROOT, False)

        self.assertEqual(res, mtime)
        self.assertTrue(Path(record_filename).exists())

    def test_get_timestamp_remove(self):
        record_filename, mtime = _get_timestamp_setup()

        Settings.record_timestamp = True
        res = timestamp._get_timestamp(TEST_FILES_ROOT, True)

        self.assertEqual(res, mtime)
        self.assertTrue(record_filename in timestamp.OLD_TIMESTAMPS)
