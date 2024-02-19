"""PNG format."""
from io import BufferedReader, BytesIO
from types import MappingProxyType
from typing import Any

import oxipng
from PIL.GifImagePlugin import GifImageFile
from PIL.PngImagePlugin import PngImageFile
from termcolor import cprint

from picopt.formats import CONVERTIBLE_FORMAT_STRS, FileFormat
from picopt.handlers.image import ImageHandler
from picopt.pillow.png_bit_depth import png_bit_depth


class Png(ImageHandler):
    """PNG format class."""

    OUTPUT_FORMAT_STR = PngImageFile.format
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, True, False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    CONVERT_FROM_FORMAT_STRS = frozenset(
        CONVERTIBLE_FORMAT_STRS | {GifImageFile.format}
    )
    PROGRAMS = (
        ("pil2png",),
        ("internal_oxipng",),
        ("pngout",),
    )
    PIL2_KWARGS = MappingProxyType({"optimize": True})
    _OXIPNG_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {
            "level": 5,
            "fix_errors": True,
            "force": True,
            "optimize_alpha": True,
            "deflate": oxipng.Deflaters.zopfli(15),
        }
    )
    _PNGOUT_ARGS: tuple[str, ...] = ("-", "-", "-force", "-y", "-q")
    _PNGOUT_DEPTH_MAX = 8

    def internal_oxipng(
        self, _exec_args: tuple[str, ...], input_buffer: BufferedReader | BytesIO
    ) -> BytesIO:
        """Run internal oxipng on the file."""
        opts = {**self._OXIPNG_KWARGS}
        if not self.config.keep_metadata:
            opts["strip"] = oxipng.StripChunks.safe()
        input_buffer.seek(0)
        with input_buffer:
            result = oxipng.optimize_from_memory(input_buffer.read(), **opts)
        return BytesIO(result)

    def pngout(
        self,
        exec_args: tuple[str, ...],
        input_buffer: BufferedReader | BytesIO,
    ) -> BytesIO | BufferedReader:
        """Run the external program pngout on the file."""
        depth = png_bit_depth(input_buffer)
        if not depth or depth > self._PNGOUT_DEPTH_MAX or depth < 1:
            cprint(
                f"Skipped pngout for {depth} bit PNG: {self.original_path}",
                "white",
                attrs=["dark"],
            )
            return input_buffer
        opts = ("-k1",) if self.config.keep_metadata else ("-k0",)
        args = (*exec_args, *self._PNGOUT_ARGS, *opts)
        return self.run_ext(args, input_buffer)
