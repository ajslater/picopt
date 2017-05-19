"""Test comic format."""
import math
import os
import time
from unittest import TestCase

from picopt import timestamp
from picopt.settings import Settings

TEST_FILES_ROOT = 'tests/test_files'
COMIC_ROOT = TEST_FILES_ROOT+'/comic_archives'


class TestTimestamp(TestCase):

    def test_get_timestamp_ne(self):
        path = os.path.join(TEST_FILES_ROOT, 'BLARGH')
        res = timestamp._get_timestamp(path, False)
        self.assertEqual(res, None)

    def test_get_timestamp_no_remove(self):
        dirname_full = TEST_FILES_ROOT
        record_filename = os.path.join(dirname_full,
                                       timestamp.RECORD_FILENAME)
        mtime = time.time()
        with open(record_filename, 'a'):
            os.utime(record_filename, (mtime, mtime))
        res = timestamp._get_timestamp(dirname_full, False)

        self.assertEqual(res, math.floor(mtime))
        self.assertTrue(os.path.exists(record_filename))

    def test_get_timestamp_remove(self):
        dirname_full = TEST_FILES_ROOT
        record_filename = os.path.join(dirname_full,
                                       timestamp.RECORD_FILENAME)
        mtime = time.time()
        with open(record_filename, 'a'):
            os.utime(record_filename, (mtime, mtime))

        # Reset the timestamp cache
        timestamp.TIMESTAMP_CACHE = {}
        Settings.record_timestamp = True
        res = timestamp._get_timestamp(dirname_full, True)

        self.assertEqual(res, math.floor(mtime))
        self.assertTrue(record_filename in timestamp.OLD_TIMESTAMPS)
