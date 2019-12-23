"""Test detect file formats."""
from pathlib import Path
from typing import Callable, Optional, Set, Tuple
from unittest import TestCase

from picopt import detect_format
from picopt.extern import ExtArgs
from picopt.formats.comic import Comic
from picopt.settings import Settings
from PIL import Image  # type: ignore

TEST_FILES_ROOT = 'tests/test_files/'
IMAGES_ROOT = TEST_FILES_ROOT+'/images'
INVALID_ROOT = TEST_FILES_ROOT+'/invalid'
COMIC_ROOT = TEST_FILES_ROOT+'/comic_archives'


class TestIsProgramSelected(TestCase):

    @staticmethod
    def pngout(args: ExtArgs) -> str:
        return 'foo'

    programs = (pngout,)

    def test_pngout(self) -> None:
        res = detect_format._is_program_selected(self.programs)
        self.assertTrue(res)

    def test_empty(self) -> None:
        res = detect_format._is_program_selected(tuple())
        self.assertFalse(res)


class TestIsFormatSelected(TestCase):

    formats: Set[str] = set(['GIF'])

    @staticmethod
    def pngout(args: ExtArgs) -> str:
        return ''

    @staticmethod
    def comics(args: ExtArgs) -> str:
        return ''

    programs: Tuple[Callable[[ExtArgs], str], ...] = (pngout, comics)

    def test_gif(self) -> None:
        res = detect_format.is_format_selected('GIF', self.formats,
                                               self.programs)
        self.assertTrue(res)

    def test_cbz_in_settings(self) -> None:
        res = detect_format.is_format_selected('CBZ', self.formats,
                                               self.programs)
        self.assertFalse(res)

    def test_cbz_not_in_settings(self) -> None:
        res = detect_format.is_format_selected('CBZ', set(['CBR']),
                                               self.programs)
        self.assertFalse(res)


class TestIsImageSequenced(TestCase):

    def test_animated_gif(self) -> None:
        image = Image.open(IMAGES_ROOT+'/test_animated_gif.gif')
        res = detect_format._is_image_sequenced(image)
        self.assertTrue(res)

    def test_normal_gif(self) -> None:
        image = Image.open(IMAGES_ROOT+'/test_gif.gif')
        res = detect_format._is_image_sequenced(image)
        self.assertFalse(res)


class TestGetImageFormat(TestCase):

    def _test_type(self, root: str, filename: str,
                   image_type: str) -> None:
        path = Path(root+'/'+filename)
        res = detect_format.get_image_format(path)
        print(res)
        self.assertEqual(res, image_type)

    def test_get_image_format_jpg(self) -> None:
        self._test_type(IMAGES_ROOT, 'test_jpg.jpg', 'JPEG')

    def test_get_image_format_png(self) -> None:
        self._test_type(IMAGES_ROOT, 'test_png.png', 'PNG')

    def test_get_image_format_gif(self) -> None:
        self._test_type(IMAGES_ROOT, 'test_gif.gif', 'GIF')

    def test_get_image_format_txt(self) -> None:
        self._test_type(IMAGES_ROOT, 'test_txt.txt', 'ERROR')

    def test_get_image_format_invalid(self) -> None:
        self._test_type(INVALID_ROOT, 'test_gif.gif', 'ERROR')

    def test_get_image_format_cbr(self) -> None:
        self._test_type(COMIC_ROOT, 'test_cbr.cbr', 'CBR')

    def test_get_image_format_cbz(self) -> None:
        self._test_type(COMIC_ROOT, 'test_cbz.cbz', 'CBZ')


class TestDetectFile(TestCase):

    class DummySettings(object):
        formats: Set[str] = set(['CBR', 'CBZ'])
        comics: bool = True
        list_only: bool = False

    def _test_type(self, root: str, filename: str,
                   image_type: Optional[str]) -> None:
        path = Path(root+'/'+filename)
        res = detect_format.detect_file(path)
        print(res)
        self.assertEqual(res, image_type)

    def test_detect_file_jpg(self) -> None:
        self._test_type(IMAGES_ROOT, 'test_jpg.jpg', 'JPEG')

    def test_detect_file_png(self) -> None:
        self._test_type(IMAGES_ROOT, 'test_png.png', 'PNG')

    def test_detect_file_gif(self) -> None:
        self._test_type(IMAGES_ROOT, 'test_gif.gif', 'GIF')

    def test_detect_file_txt(self) -> None:
        self._test_type(IMAGES_ROOT, 'test_txt.txt', None)

    def test_detect_file_invalid(self) -> None:
        self._test_type(INVALID_ROOT, 'test_gif.gif', None)

    def test_detect_file_cbr(self) -> None:
        Settings.formats = Settings.formats | Comic.FORMATS
        self._test_type(COMIC_ROOT, 'test_cbr.cbr', 'CBR')

    def test_detect_file_cbz(self) -> None:
        Settings.formats = Settings.formats | Comic.FORMATS
        self._test_type(COMIC_ROOT, 'test_cbz.cbz', 'CBZ')
