"""Test detect file format module."""
from pathlib import Path
from typing import Callable, Optional, Set, Tuple

from picopt import detect_format
from picopt.extern import ExtArgs
from picopt.formats.comic_formats import COMIC_FORMATS
from picopt.settings import Settings
from tests import COMIC_DIR, IMAGES_DIR, INVALID_DIR


__all__ = ()  # hides module from pydocstring


class TestIsProgramSelected:
    @staticmethod
    def pngout(_: ExtArgs) -> str:
        return ""

    @staticmethod
    def comics(_: ExtArgs) -> str:
        return ""

    programs_true = (pngout, comics)
    programs_false = (comics,)

    def setup_method(self):
        self.settings = Settings()

    def test_comics(self) -> None:
        res = detect_format._is_program_selected(self.settings, self.programs_false)
        assert not res

    def test_pngout(self) -> None:
        res = detect_format._is_program_selected(self.settings, self.programs_true)
        assert res

    def test_empty(self) -> None:
        res = detect_format._is_program_selected(self.settings, tuple())
        assert not res


class TestIsFormatSelected:
    @staticmethod
    def pngout(_: ExtArgs) -> str:
        return ""

    @staticmethod
    def comics(_: ExtArgs) -> str:
        return ""

    formats: Set[str] = set(["GIF"])

    programs: Tuple[Callable[[ExtArgs], str], ...] = (pngout, comics)

    def setup_method(self):
        self.settings = Settings()

    def test_gif(self) -> None:
        res = detect_format.is_format_selected(
            self.settings, "GIF", self.formats, self.programs
        )
        assert res

    def test_cbz_in_settings(self) -> None:
        res = detect_format.is_format_selected(
            self.settings, "CBZ", self.formats, self.programs
        )
        assert not res

    def test_cbz_not_in_settings(self) -> None:
        res = detect_format.is_format_selected(
            self.settings, "CBZ", set(["CBR"]), self.programs
        )
        assert not res


class TestGetImageFormat:
    def _test_type(self, root: Path, filename: str, image_type: Optional[str]) -> None:
        path = root / filename
        res = detect_format._get_image_format(path)
        assert res == image_type

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


class TestDetectFile:
    def setup_method(self):
        self.settings = Settings()

    def _test_type(self, root: Path, filename: str, image_type: Optional[str]) -> None:
        path = root / filename
        res = detect_format.detect_file(self.settings, path)
        print(res)
        assert res == image_type

    def test_detect_file_jpg(self) -> None:
        self._test_type(IMAGES_DIR, "test_jpg.jpg", "JPEG")

    def test_detect_file_png(self) -> None:
        self._test_type(IMAGES_DIR, "test_png.png", "PNG")

    def test_detect_file_gif(self) -> None:
        self._test_type(IMAGES_DIR, "test_gif.gif", "GIF")

    def test_detect_file_txt(self) -> None:
        self.settings.verbose = 2
        self._test_type(IMAGES_DIR, "test_txt.txt", None)

    def test_detect_file_txt_quiet(self) -> None:
        self.settings.verbose = 0
        self._test_type(IMAGES_DIR, "test_txt.txt", None)

    def test_detect_file_invalid(self) -> None:
        self._test_type(INVALID_DIR, "test_gif.gif", None)

    def test_detect_file_cbr(self) -> None:
        self.settings.formats |= COMIC_FORMATS
        self._test_type(COMIC_DIR, "test_cbr.cbr", "CBR")

    def test_detect_file_cbz(self) -> None:
        self.settings.formats |= COMIC_FORMATS
        self._test_type(COMIC_DIR, "test_cbz.cbz", "CBZ")
