from unittest import TestCase

try:
    from PIL import Image
except ImportError:
    import Image

from picopt.formats import comic
from picopt import detect_format
from picopt.settings import Settings


TEST_FILES_ROOT = 'tests/test_files/'
IMAGES_ROOT = TEST_FILES_ROOT+'/images'
INVALID_ROOT = TEST_FILES_ROOT+'/invalid'
COMIC_ROOT = TEST_FILES_ROOT+'/comic_archives'


class TestIsProgramSelected(TestCase):

    def pngout(self):
        pass

    programs = (pngout,)

    def test_pngout(self):
        res = detect_format._is_program_selected(self.programs)
        self.assertTrue(res)

    def test_empty(self):
        res = detect_format._is_program_selected([])
        self.assertFalse(res)


class TestIsFormatSelected(TestCase):

    formats = set(['GIF'])

    def pngout(self):
        pass

    def comics(self):
        pass

    programs = (pngout, comics)

    def test_GIF(self):
        res = detect_format.is_format_selected('GIF', self.formats,
                                               self.programs)
        self.assertTrue(res)

    def test_CBZ_in_settings(self):
        res = detect_format.is_format_selected('CBZ', self.formats,
                                               self.programs)
        self.assertFalse(res)

    def test_CBZ_not_in_settings(self):
        res = detect_format.is_format_selected('CBZ', set(['CBR']),
                                               self.programs)
        self.assertFalse(res)


class TestIsImageSequenced(TestCase):

    def test_animated_gif(self):
        image = Image.open(IMAGES_ROOT+'/test_animated_gif.gif')
        res = detect_format._is_image_sequenced(image)
        self.assertTrue(res)

    def test_normal_gif(self):
        image = Image.open(IMAGES_ROOT+'/test_gif.gif')
        res = detect_format._is_image_sequenced(image)
        self.assertFalse(res)


class TestGetImageFormat(TestCase):

    def _test_type(self, root, filename, image_type):
        fn = root+'/'+filename
        res = detect_format.get_image_format(fn)
        print res
        self.assertEqual(res, image_type)

    def test_get_image_format_jpg(self):
        self._test_type(IMAGES_ROOT, 'test_jpg.jpg', 'JPEG')

    def test_get_image_format_png(self):
        self._test_type(IMAGES_ROOT, 'test_png.png', 'PNG')

    def test_get_image_format_gif(self):
        self._test_type(IMAGES_ROOT, 'test_gif.gif', 'GIF')

    def test_get_image_format_txt(self):
        self._test_type(IMAGES_ROOT, 'test_txt.txt', 'ERROR')

    def test_get_image_format_invalid(self):
        self._test_type(INVALID_ROOT, 'test_gif.gif', 'ERROR')

    def test_get_image_format_cbr(self):
        self._test_type(COMIC_ROOT, 'test_cbr.cbr', 'CBR')

    def test_get_image_format_cbz(self):
        self._test_type(COMIC_ROOT, 'test_cbz.cbz', 'CBZ')


class TestDetectFile(TestCase):

    class DummySettings(object):
        formats = ('CBR', 'CBZ')
        comics = True
        list_only = False

    def _test_type(self, root, filename, image_type):
        fn = root+'/'+filename
        res = detect_format.detect_file(fn)
        print res
        self.assertEqual(res, image_type)

    def test_detect_file_jpg(self):
        self._test_type(IMAGES_ROOT, 'test_jpg.jpg', 'JPEG')

    def test_detect_file_png(self):
        self._test_type(IMAGES_ROOT, 'test_png.png', 'PNG')

    def test_detect_file_gif(self):
        self._test_type(IMAGES_ROOT, 'test_gif.gif', 'GIF')

    def test_detect_file_txt(self):
        self._test_type(IMAGES_ROOT, 'test_txt.txt', None)

    def test_detect_file_invalid(self):
        self._test_type(INVALID_ROOT, 'test_gif.gif', None)

    def test_detect_file_cbr(self):
        Settings.formats = Settings.formats | comic.FORMATS
        self._test_type(COMIC_ROOT, 'test_cbr.cbr', 'CBR')

    def test_detect_file_cbz(self):
        Settings.formats = Settings.formats | comic.FORMATS
        self._test_type(COMIC_ROOT, 'test_cbz.cbz', 'CBZ')
