from unittest import TestCase

from picopt import detect_format


class TestDetectFormat(TestCase):

    def test_detect_file_jpg(self):

        res = detect_format.detect_file(
            'old_tests/test_tmp/images/test_jpg.jpg')
        self.assertTrue(res, 'JPEG')
