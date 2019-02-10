"""Test comic format."""
from __future__ import absolute_import, division, print_function

import math
import os
import time
from unittest import TestCase

from picopt import timestamp
from picopt.settings import Settings

TEST_FILES_ROOT = 'tests/test_files'
COMIC_ROOT = TEST_FILES_ROOT+'/comic_archives'


def _get_timestamp_setup():
    record_filename = os.path.join(TEST_FILES_ROOT,
                                   timestamp.RECORD_FILENAME)

    mtime = math.floor(time.time())
    with open(record_filename, 'a'):
        os.utime(record_filename, (mtime, mtime))
    return record_filename, mtime



class TestTimestamp(TestCase):

    def test_get_timestamp_ne(self):
        path = os.path.join(TEST_FILES_ROOT, 'BLARGH')
        res = timestamp._get_timestamp(path, False)
        self.assertEqual(res, None)

    def test_get_timestamp_no_remove(self):
        record_filename, mtime = _get_timestamp_setup()
        res = timestamp._get_timestamp(TEST_FILES_ROOT, False)

        self.assertEqual(res, mtime)
        self.assertTrue(os.path.exists(record_filename))

    def test_get_timestamp_remove(self):
        record_filename, mtime = _get_timestamp_setup()

        Settings.record_timestamp = True
        res = timestamp._get_timestamp(TEST_FILES_ROOT, True)

        self.assertEqual(res, mtime)
        self.assertTrue(record_filename in timestamp.OLD_TIMESTAMPS)
