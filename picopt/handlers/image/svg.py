"""WebP format."""

from io import BytesIO
from typing import BinaryIO

from picopt.formats import SVG_FORMAT_STR, FileFormat
from picopt.handlers.image import ImageHandler
from picopt.handlers.mixins import NonPILIdentifierMixin


class Svg(ImageHandler, NonPILIdentifierMixin):
    """SVG format class."""

    OUTPUT_FORMAT_STR: str = SVG_FORMAT_STR
    SUFFIXES: tuple[str, ...] = (".svg",)
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(
        OUTPUT_FORMAT_STR, lossless=True, animated=False
    )
    INPUT_FILE_FORMAT: FileFormat = OUTPUT_FILE_FORMAT
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset({INPUT_FILE_FORMAT})
    PROGRAMS: tuple[tuple[str, ...], ...] = (("svgo", "npx_svgo"),)
    _SVGO_ARGS: tuple[str, ...] = ("--multipass", "--output", "-", "--input", "-")

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
