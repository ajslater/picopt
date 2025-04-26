"""WebP format."""

from abc import ABC
from io import BytesIO
from types import MappingProxyType
from typing import TYPE_CHECKING, BinaryIO

from confuse import AttrDict
from PIL.WebPImagePlugin import WebPImageFile

from picopt.formats import MODERN_CWEBP_FORMATS, FileFormat
from picopt.handlers.image import ImageHandler
from picopt.handlers.image.png import Png

if TYPE_CHECKING:
    from pathlib import Path


class WebPBase(ImageHandler, ABC):
    """Base for handlers that use WebP utility commands."""

    PIL2_KWARGS = MappingProxyType({"quality": 100, "method": 6})
    OUTPUT_FORMAT_STR = str(WebPImageFile.format)
    PROGRAMS = (("cwebp", "pil2native"),)
    # https://developers.google.com/speed/webp/docs/cwebp
    CWEBP_ARGS_PREFIX = (
        "-mt",
        "-q",
        "100",
        "-m",
        "6",
        # advanced
        "-sharp_yuv",
        # logging,
        "-quiet",
        # additional
        "-alpha_filter",
        "best",
    )

    def cwebp(
        self,
        exec_args: tuple[str, ...],
        input_buffer: BinaryIO,
        opts: tuple[str, ...] | None = None,
    ) -> BinaryIO:
        """Optimize using cwebp."""
        args = [*exec_args]
        if opts:
            args += [*opts]
        args += [*self.CWEBP_ARGS_PREFIX]
        args += ["-metadata"]
        if self.config.keep_metadata:
            args += ["all"]
        else:
            args += ["none"]

        input_path_tmp = isinstance(input_buffer, BytesIO)
        input_path: Path | None = (
            self.get_working_path("cwebp-input")
            if input_path_tmp
            else self.path_info.path
        )
        if not input_path:
            reason = "No input path for cwebp"
            raise ValueError(reason)

        output_path = self.get_working_path("cwebp-output")
        output_path_tmp = bool(self.path_info.path)
        args += [str(input_path), "-o", str(output_path)]
        # If python cwebp gains enough options to beat this or
        #     or cwebp gains stdin or stdout powers we can be rid of this
        return self.run_ext_fs(
            tuple(args),
            input_buffer,
            input_path,
            output_path,
            input_path_tmp=input_path_tmp,
            output_path_tmp=output_path_tmp,
        )


class WebPLossless(WebPBase):
    """Handle lossless webp images and images that convert to lossless webp."""

    OUTPUT_FILE_FORMAT = FileFormat(
        WebPBase.OUTPUT_FORMAT_STR, lossless=True, animated=False
    )
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT, Png.OUTPUT_FILE_FORMAT})
    CWEBP_ARGS_PREFIX = (
        # https://groups.google.com/a/webmproject.org/g/webp-discuss/c/0GmxDmlexek
        "-lossless",
        *WebPBase.CWEBP_ARGS_PREFIX,
    )
    PIL2_KWARGS = MappingProxyType({**WebPBase.PIL2_KWARGS, "lossless": True})
    PROGRAMS = (("pil2png",), ("cwebp", "pil2native"))
    _NEAR_LOSSLESS_OPTS: tuple[str, ...] = ("-near_lossless", "0")

    def __init__(self, config: AttrDict, *args, **kwargs):
        """Initialize extra input formats."""
        super().__init__(config, *args, **kwargs)
        if config.computed.is_modern_cwebp:
            self._input_file_formats |= MODERN_CWEBP_FORMATS

    def cwebp(
        self,
        exec_args: tuple[str, ...],
        input_buffer: BinaryIO,
        opts: tuple[str, ...] | None = None,
    ) -> BinaryIO:
        """Optimize using cwebp and with runtime optional arguments."""
        opts = self._NEAR_LOSSLESS_OPTS if self.config.near_lossless else None
        return super().cwebp(exec_args, input_buffer, opts=opts)
