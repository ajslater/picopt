from unittest import TestCase

from picopt import detect_format

IMAGES_ROOT = 'old_tests/test_files/images'


class TestDetectFormat(TestCase):

    def _test_type(self, filename, image_type):
        fn = IMAGES_ROOT+'/'+filename
        res = detect_format.detect_file(fn)
        self.assertTrue(res, image_type)

    def test_detect_file_jpg(self):
        self._test_type('test_jpg.jpg', 'JPEG')

    def test_detect_file_png(self):
        self._test_type('test_png.png', 'PNG')

    def test_detect_file_gif(self):
        self._test_type('test_gif.gif', 'GIF')
