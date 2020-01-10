"""Test detect file format module."""
from pathlib import Path
from typing import Callable
from typing import Optional
from typing import Set
from typing import Tuple
from unittest import TestCase

from picopt import detect_format
from picopt.extern import ExtArgs
from picopt.formats.comic import Comic
from picopt.settings import Settings


__all__ = ()  # hides module from pydocstring
TEST_FILES_ROOT = "tests/test_files/"
IMAGES_ROOT = TEST_FILES_ROOT + "/images"
INVALID_ROOT = TEST_FILES_ROOT + "/invalid"
COMIC_ROOT = TEST_FILES_ROOT + "/comic_archives"
SETTINGS = Settings(set(), None)


class TestIsProgramSelected(TestCase):
    @staticmethod
    def pngout(settings: Settings, args: ExtArgs) -> str:
        return ""

    @staticmethod
    def comics(settings: Settings, args: ExtArgs) -> str:
        return ""

    programs_true = (pngout, comics)
    programs_false = (comics,)

    def test_comics(self) -> None:
        res = detect_format._is_program_selected(SETTINGS, self.programs_false)
        self.assertFalse(res)

    def test_pngout(self) -> None:
        res = detect_format._is_program_selected(SETTINGS, self.programs_true)
        self.assertTrue(res)

    def test_empty(self) -> None:
        res = detect_format._is_program_selected(SETTINGS, tuple())
        self.assertFalse(res)


class TestIsFormatSelected(TestCase):
    @staticmethod
    def pngout(settings: Settings, args: ExtArgs) -> str:
        return ""

    @staticmethod
    def comics(settings: Settings, args: ExtArgs) -> str:
        return ""

    formats: Set[str] = set(["GIF"])

    programs: Tuple[Callable[[Settings, ExtArgs], str], ...] = (pngout, comics)

    def test_gif(self) -> None:
        print(SETTINGS.formats)
        res = detect_format.is_format_selected(
            SETTINGS, "GIF", self.formats, self.programs
        )
        self.assertTrue(res)

    def test_cbz_in_settings(self) -> None:
        res = detect_format.is_format_selected(
            SETTINGS, "CBZ", self.formats, self.programs
        )
        self.assertFalse(res)

    def test_cbz_not_in_settings(self) -> None:
        res = detect_format.is_format_selected(
            SETTINGS, "CBZ", set(["CBR"]), self.programs
        )
        self.assertFalse(res)


class TestGetImageFormat(TestCase):
    def _test_type(self, root: str, filename: str, image_type: Optional[str]) -> None:
        path = Path(root + "/" + filename)
        res = detect_format.get_image_format(path)
        self.assertEqual(res, image_type)

    def test_get_image_format_jpg(self) -> None:
        self._test_type(IMAGES_ROOT, "test_jpg.jpg", "JPEG")

    def test_get_image_format_png(self) -> None:
        self._test_type(IMAGES_ROOT, "test_png.png", "PNG")

    def test_get_image_format_gif(self) -> None:
        self._test_type(IMAGES_ROOT, "test_gif.gif", "GIF")

    def test_get_image_format_animated_gif(self) -> None:
        self._test_type(IMAGES_ROOT, "test_animated_gif.gif", "ANIMATED_GIF")

    def test_get_image_format_txt(self) -> None:
        self._test_type(IMAGES_ROOT, "test_txt.txt", None)

    def test_get_image_format_invalid(self) -> None:
        self._test_type(INVALID_ROOT, "test_gif.gif", None)

    def test_get_image_format_cbr(self) -> None:
        self._test_type(COMIC_ROOT, "test_cbr.cbr", "CBR")

    def test_get_image_format_cbz(self) -> None:
        self._test_type(COMIC_ROOT, "test_cbz.cbz", "CBZ")

    def test_get_image_format_unsupported(self) -> None:
        self._test_type(INVALID_ROOT, "test_mpeg.mpeg", "MPEG")


class TestDetectFile(TestCase):
    class DummySettings(object):
        formats: Set[str] = set(["CBR", "CBZ"])
        comics: bool = True
        list_only: bool = False

    def _test_type(
        self, settings: Settings, root: str, filename: str, image_type: Optional[str]
    ) -> None:
        path = Path(root + "/" + filename)
        res = detect_format.detect_file(settings, path)
        print(res)
        self.assertEqual(res, image_type)

    def test_detect_file_jpg(self) -> None:
        self._test_type(SETTINGS, IMAGES_ROOT, "test_jpg.jpg", "JPEG")

    def test_detect_file_png(self) -> None:
        self._test_type(SETTINGS, IMAGES_ROOT, "test_png.png", "PNG")

    def test_detect_file_gif(self) -> None:
        self._test_type(SETTINGS, IMAGES_ROOT, "test_gif.gif", "GIF")

    def test_detect_file_txt(self) -> None:
        settings = Settings(namespace=SETTINGS)
        settings.verbose = 2
        self._test_type(settings, IMAGES_ROOT, "test_txt.txt", None)

    def test_detect_file_txt_quiet(self) -> None:
        settings = Settings(namespace=SETTINGS)
        settings.verbose = 0
        self._test_type(settings, IMAGES_ROOT, "test_txt.txt", None)

    def test_detect_file_invalid(self) -> None:
        self._test_type(SETTINGS, INVALID_ROOT, "test_gif.gif", None)

    def test_detect_file_cbr(self) -> None:
        settings = Settings(namespace=SETTINGS)
        settings.formats |= Comic.FORMATS
        self._test_type(settings, COMIC_ROOT, "test_cbr.cbr", "CBR")

    def test_detect_file_cbz(self) -> None:
        settings = Settings(namespace=SETTINGS)
        settings.formats |= Comic.FORMATS
        self._test_type(settings, COMIC_ROOT, "test_cbz.cbz", "CBZ")
