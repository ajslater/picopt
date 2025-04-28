"""PNG format."""

from abc import ABC
from io import BufferedReader, BytesIO
from types import MappingProxyType
from typing import Any

import oxipng
from PIL.PngImagePlugin import PngImageFile

from picopt.formats import FileFormat
from picopt.handlers.image import ImageHandler
from picopt.pillow.png_bit_depth import png_bit_depth


class PngBase(ImageHandler, ABC):
    """Abstract image handler that uses OxiPng."""

    _OXIPNG_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {
            "level": 3,
            "fix_errors": True,
            "force": True,
            "optimize_alpha": True,
        }
    )
    _OXIPNG_MAX_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {
            "level": 5,
            "deflate": oxipng.Deflaters.zopfli(15),
        }
    )
    PROGRAMS = (("pil2png",), ("internal_oxipng",))
    PIL2_KWARGS = MappingProxyType({"optimize": True})

    def internal_oxipng(
        self, _exec_args: tuple[str, ...], input_buffer: BufferedReader | BytesIO
    ) -> BytesIO:
        """Run internal oxipng on the file."""
        oxipng_kwargs = self._OXIPNG_KWARGS
        if self.config.png_max:
            oxipng_kwargs = dict(oxipng_kwargs)
            oxipng_kwargs.update(self._OXIPNG_MAX_KWARGS)
        opts = {**self._OXIPNG_KWARGS}
        if not self.config.keep_metadata:
            opts["strip"] = oxipng.StripChunks.safe()
        input_buffer.seek(0)
        with input_buffer:
            result = oxipng.optimize_from_memory(input_buffer.read(), **opts)
        return BytesIO(result)


class Png(PngBase):
    """PNG format class."""

    OUTPUT_FORMAT_STR = str(PngImageFile.format)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, lossless=True, animated=False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS = (
        *PngBase.PROGRAMS,
        ("pngout",),
    )
    _PNGOUT_ARGS: tuple[str, ...] = ("-", "-", "-force", "-y", "-q")
    _PNGOUT_DEPTH_MAX = 8

    def pngout(
        self,
        exec_args: tuple[str, ...],
        input_buffer: BufferedReader | BytesIO,
    ) -> BytesIO | BufferedReader:
        """Run the external program pngout on the file."""
        depth = png_bit_depth(input_buffer)
        if not depth or depth > self._PNGOUT_DEPTH_MAX or depth < 1:
            self._printer.skip_message(
                f"Skipped pngout for {depth} bit PNG: {self.path_info.full_output_name()}",
            )
            return input_buffer
        opts = ("-k1",) if self.config.keep_metadata else ("-k0",)
        args = (*exec_args, *self._PNGOUT_ARGS, *opts)
        return self.run_ext(args, input_buffer)


class PngAnimated(PngBase):
    """Animated Png container."""

    OUTPUT_FORMAT_STR: str = Png.OUTPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, lossless=True, animated=True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
