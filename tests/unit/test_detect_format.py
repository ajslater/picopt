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
from tests import COMIC_DIR
from tests import IMAGES_DIR
from tests import INVALID_DIR


__all__ = ()  # hides module from pydocstring


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
        res = detect_format._is_program_selected(Settings(), self.programs_false)
        self.assertFalse(res)

    def test_pngout(self) -> None:
        res = detect_format._is_program_selected(Settings(), self.programs_true)
        self.assertTrue(res)

    def test_empty(self) -> None:
        res = detect_format._is_program_selected(Settings(), tuple())
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
        res = detect_format.is_format_selected(
            Settings(), "GIF", self.formats, self.programs
        )
        self.assertTrue(res)

    def test_cbz_in_settings(self) -> None:
        res = detect_format.is_format_selected(
            Settings(), "CBZ", self.formats, self.programs
        )
        self.assertFalse(res)

    def test_cbz_not_in_settings(self) -> None:
        res = detect_format.is_format_selected(
            Settings(), "CBZ", set(["CBR"]), self.programs
        )
        self.assertFalse(res)


class TestGetImageFormat(TestCase):
    def _test_type(self, root: Path, filename: str, image_type: Optional[str]) -> None:
        path = root / filename
        res = detect_format.get_image_format(path)
        self.assertEqual(res, image_type)

    def test_get_image_format_jpg(self) -> None:
        self._test_type(IMAGES_DIR, "test_jpg.jpg", "JPEG")

    def test_get_image_format_png(self) -> None:
        self._test_type(IMAGES_DIR, "test_png.png", "PNG")

    def test_get_image_format_gif(self) -> None:
        self._test_type(IMAGES_DIR, "test_gif.gif", "GIF")

    def test_get_image_format_animated_gif(self) -> None:
        self._test_type(IMAGES_DIR, "test_animated_gif.gif", "ANIMATED_GIF")

    def test_get_image_format_txt(self) -> None:
        self._test_type(IMAGES_DIR, "test_txt.txt", None)

    def test_get_image_format_invalid(self) -> None:
        self._test_type(INVALID_DIR, "test_gif.gif", None)

    def test_get_image_format_cbr(self) -> None:
        self._test_type(COMIC_DIR, "test_cbr.cbr", "CBR")

    def test_get_image_format_cbz(self) -> None:
        self._test_type(COMIC_DIR, "test_cbz.cbz", "CBZ")

    def test_get_image_format_unsupported(self) -> None:
        self._test_type(INVALID_DIR, "test_mpeg.mpeg", "MPEG")


class TestDetectFile(TestCase):
    def _test_type(
        self, settings: Settings, root: Path, filename: str, image_type: Optional[str]
    ) -> None:
        path = root / filename
        res = detect_format.detect_file(settings, path)
        print(res)
        self.assertEqual(res, image_type)

    def test_detect_file_jpg(self) -> None:
        self._test_type(Settings(), IMAGES_DIR, "test_jpg.jpg", "JPEG")

    def test_detect_file_png(self) -> None:
        self._test_type(Settings(), IMAGES_DIR, "test_png.png", "PNG")

    def test_detect_file_gif(self) -> None:
        self._test_type(Settings(), IMAGES_DIR, "test_gif.gif", "GIF")

    def test_detect_file_txt(self) -> None:
        settings = Settings(namespace=Settings())
        settings.verbose = 2
        self._test_type(settings, IMAGES_DIR, "test_txt.txt", None)

    def test_detect_file_txt_quiet(self) -> None:
        settings = Settings(namespace=Settings())
        settings.verbose = 0
        self._test_type(settings, IMAGES_DIR, "test_txt.txt", None)

    def test_detect_file_invalid(self) -> None:
        self._test_type(Settings(), INVALID_DIR, "test_gif.gif", None)

    def test_detect_file_cbr(self) -> None:
        settings = Settings(namespace=Settings())
        settings.formats |= Comic.FORMATS
        self._test_type(settings, COMIC_DIR, "test_cbr.cbr", "CBR")

    def test_detect_file_cbz(self) -> None:
        settings = Settings(namespace=Settings())
        settings.formats |= Comic.FORMATS
        self._test_type(settings, COMIC_DIR, "test_cbz.cbz", "CBZ")
