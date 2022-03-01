"""Test detect file format module."""
from argparse import Namespace
from pathlib import Path
from typing import Optional, Type

from picopt.config import get_config
from picopt.handlers.get_handler import get_handler
from picopt.handlers.gif import Gif
from picopt.handlers.handler import Handler
from picopt.handlers.jpeg import Jpeg
from picopt.handlers.png import Png
from picopt.handlers.webp import Gif2WebP, WebPLossless, WebPLossy
from picopt.handlers.zip import CBZ, Zip
from tests import CONTAINER_DIR, IMAGES_DIR, INVALID_DIR


__all__ = ()  # hides module from pydocstring


class TestDetectFile:
    def _test_type(
        self,
        root: Path,
        filename: str,
        handler: Optional[Type[Handler]],
        args: Optional[Namespace] = None,
    ) -> None:

        config = get_config(args)
        path = root / filename
        res = get_handler(config, path)
        assert res == handler

    def test_detect_file_jpg(self) -> None:
        self._test_type(IMAGES_DIR, "test_jpg.jpg", Jpeg)

    def test_detect_file_png(self) -> None:
        self._test_type(IMAGES_DIR, "test_png.png", Png)

    def test_detect_file_gif(self) -> None:
        self._test_type(IMAGES_DIR, "test_gif.gif", Gif)

    def test_detect_file_animated_gif(self) -> None:
        self._test_type(IMAGES_DIR, "test_animated_gif.gif", Gif)

    def test_detect_file_webp_lossless(self) -> None:
        self._test_type(IMAGES_DIR, "test_webp_lossless.webp", WebPLossless)

    def test_detect_file_webp_lossy(self) -> None:
        self._test_type(IMAGES_DIR, "test_webp_lossy.webp", WebPLossy)

    def test_detect_file_animated_gif_convert(self) -> None:
        args = Namespace(convert_to={"WEBP": True})
        self._test_type(IMAGES_DIR, "test_animated_gif.gif", Gif2WebP, args)

    def test_detect_file_png_convert(self) -> None:
        args = Namespace(convert_to={"PNG": True})
        self._test_type(IMAGES_DIR, "test_bmp.bmp", Png, args)

    def test_detect_file_webp_convert(self) -> None:
        args = Namespace(convert_to={"WEBP": True})
        self._test_type(IMAGES_DIR, "test_bmp.bmp", WebPLossless, args)

    def test_detect_file_unhandled(self) -> None:
        self._test_type(IMAGES_DIR, "test_bmp.bmp", None)

    def test_detect_file_txt(self) -> None:
        args = Namespace(verbose=2)
        self._test_type(IMAGES_DIR, "test_txt.txt", None, args)

    def test_detect_file_txt_quiet(self) -> None:
        args = Namespace(verbose=0)
        self._test_type(IMAGES_DIR, "test_txt.txt", None, args)

    def test_detect_file_invalid(self) -> None:
        self._test_type(INVALID_DIR, "test_gif.gif", None)

    def test_detect_file_zip(self) -> None:
        args = Namespace(formats=set(["ZIP"]))
        self._test_type(CONTAINER_DIR, "test_zip.zip", Zip, args)

    def test_detect_file_cbz(self) -> None:
        args = Namespace(_extra_formats=["CBZ"])
        self._test_type(CONTAINER_DIR, "test_cbz.cbz", CBZ, args)
