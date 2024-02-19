"""WebP format."""
from io import BytesIO
from typing import BinaryIO

from picopt.formats import SVG_FORMAT_STR, FileFormat
from picopt.handlers.image import ImageHandler
from picopt.handlers.non_pil import NonPILIdentifier


class Svg(ImageHandler, NonPILIdentifier):
    """SVG format class."""

    OUTPUT_FORMAT_STR = SVG_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, True)
    INPUT_FORMAT_SUFFIX = "." + OUTPUT_FORMAT_STR.lower()
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS = (("svgo", "npx_svgo"),)
    _SVGO_ARGS = ("--multipass", "--output", "-", "--input", "-")

    def _svgo(self, exec_args: tuple[str, ...], input_buffer: BinaryIO) -> BytesIO:
        """Optimize using svgo."""
        args = (*exec_args, *self._SVGO_ARGS)
        return self.run_ext(args, input_buffer)

    def svgo(self, exec_args: tuple[str, ...], input_buffer: BinaryIO) -> BytesIO:
        """Svgo executable."""
        return self._svgo(exec_args, input_buffer)

    def npx_svgo(self, exec_args: tuple[str, ...], input_buffer: BinaryIO) -> BytesIO:
        """Npx installed svgo."""
        return self._svgo(exec_args, input_buffer)
