"""Gif format."""
from io import BytesIO
from types import MappingProxyType
from typing import BinaryIO

from PIL.GifImagePlugin import GifImageFile

from picopt.formats import FileFormat
from picopt.handlers.image import ImageHandler


class Gif(ImageHandler):
    """GIF handler."""

    OUTPUT_FORMAT_STR = GifImageFile.format
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, True, False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS = (("gifsicle", "pil2native"),)
    PIL2_KWARGS = MappingProxyType({"optimize": True})
    _GIFSICLE_ARGS_PREFIX: tuple[str, ...] = (
        "--optimize=3",
        "--threads",
        "--output",
        "-",
        "-",
    )

    def gifsicle(self, exec_args: tuple[str, ...], input_buffer: BinaryIO) -> BytesIO:
        """Return gifsicle args."""
        args = (*exec_args, *self._GIFSICLE_ARGS_PREFIX)
        return self.run_ext(args, input_buffer)


class GifAnimated(Gif):
    """Animated GIF handler."""

    OUTPUT_FILE_FORMAT = FileFormat(Gif.OUTPUT_FORMAT_STR, True, True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
