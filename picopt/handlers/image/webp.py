"""WebP format."""

from abc import ABC
from io import BytesIO
from types import MappingProxyType
from typing import TYPE_CHECKING, BinaryIO

from confuse import AttrDict
from PIL.WebPImagePlugin import WebPImageFile
from typing_extensions import override

from picopt.formats import MODERN_CWEBP_FORMATS, FileFormat
from picopt.handlers.image import ImageHandler
from picopt.handlers.image.gif import GifAnimated
from picopt.handlers.image.png import Png

if TYPE_CHECKING:
    from pathlib import Path


class WebPBase(ImageHandler, ABC):
    """Base for handlers that use WebP utility commands."""

    PIL2_KWARGS = MappingProxyType({"quality": 100, "method": 6})
    OUTPUT_FORMAT_STR = str(WebPImageFile.format)
    PROGRAMS: tuple[tuple[str, ...], ...] = (("cwebp", "pil2native"),)
    # https://developers.google.com/speed/webp/docs/cwebp
    WEBP_ARGS_PREFIX: tuple[str, ...] = (
        "-mt",
        "-q",
        "100",
        "-m",
        "6",
        # advanced
        "-sharp_yuv",
        # logging,
        "-quiet",
    )
    WORKING_ID: str = PROGRAMS[0][0]
    ADD_MODERN_CWEBP_FORMATS: bool = True

    def __init__(self, config: AttrDict, *args, **kwargs):
        """Initialize extra input formats."""
        super().__init__(config, *args, **kwargs)
        if self.ADD_MODERN_CWEBP_FORMATS and config.computed.is_modern_cwebp:
            self._input_file_formats |= MODERN_CWEBP_FORMATS

    def _add_webp_args(self, args: list[str], opts: tuple[str, ...] | None):
        if opts:
            args.extend(opts)
        args.extend(self.WEBP_ARGS_PREFIX)
        args.append("-metadata")
        if self.config.keep_metadata:
            args.append("all")
        else:
            args.append("none")

    def _get_input_path(self, input_buffer: BinaryIO):
        input_path_tmp = isinstance(input_buffer, BytesIO)
        input_path: Path | None = (
            self.get_working_path(f".{self.WORKING_ID}-input")
            if input_path_tmp
            else self.path_info.path
        )
        if not input_path:
            reason = "No input path for cwebp"
            raise ValueError(reason)
        return input_path, input_path_tmp

    def _get_output_path(self):
        output_path = self.get_working_path(f".{self.WORKING_ID}-output")
        output_path_tmp = bool(self.path_info.path)
        return output_path, output_path_tmp

    def _cwebp(
        self,
        exec_args: tuple[str, ...],
        input_buffer: BinaryIO,
        opts: tuple[str, ...] | None = None,
    ) -> BinaryIO:
        """Optimize using cwebp."""
        args = [*exec_args]
        self._add_webp_args(args, opts)
        input_path, input_path_tmp = self._get_input_path(input_buffer)
        output_path, output_path_tmp = self._get_output_path()

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

    def cwebp(
        self,
        exec_args: tuple[str, ...],
        input_buffer: BinaryIO,
        opts: tuple[str, ...] | None = None,
    ) -> BinaryIO:
        """Optimize using cwebp."""
        return self._cwebp(exec_args, input_buffer, opts)


class WebPLossless(WebPBase):
    """Handle lossless webp images and images that convert to lossless webp."""

    OUTPUT_FILE_FORMAT = FileFormat(
        WebPBase.OUTPUT_FORMAT_STR, lossless=True, animated=False
    )
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT, Png.OUTPUT_FILE_FORMAT})
    WEBP_ARGS_PREFIX: tuple[str, ...] = (
        # https://groups.google.com/a/webmproject.org/g/webp-discuss/c/0GmxDmlexek
        "-lossless",
        *WebPBase.WEBP_ARGS_PREFIX,
        # additional
        "-alpha_filter",
        "best",
    )
    PIL2_KWARGS = MappingProxyType({**WebPBase.PIL2_KWARGS, "lossless": True})
    PROGRAMS: tuple[tuple[str, ...], ...] = (("pil2png",), ("cwebp", "pil2native"))
    _NEAR_LOSSLESS_OPTS: tuple[str, ...] = ("-near_lossless", "0")

    @override
    def _add_webp_args(self, args, opts):
        super()._add_webp_args(args, opts)
        if self.config.near_lossless:
            args.extend(self._NEAR_LOSSLESS_OPTS)


class Gif2WebPAnimatedLossless(WebPBase):
    """Gif2AnimatedWebP."""

    OUTPUT_FORMAT_STR = str(WebPImageFile.format)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, lossless=True, animated=True)
    INPUT_FILE_FORMATS = frozenset({GifAnimated.OUTPUT_FILE_FORMAT})
    # https://developers.google.com/speed/webp/docs/gif2webp
    WEBP_ARGS_PREFIX = (*WebPBase.WEBP_ARGS_PREFIX, "-min_size")
    PIL2_KWARGS = MappingProxyType({**WebPBase.PIL2_KWARGS, "lossless": True})
    PROGRAMS = (("gif2webp",),)
    WORKING_ID = PROGRAMS[0][0]
    ADD_MODERN_CWEBP_FORMATS = False

    def gif2webp(
        self,
        exec_args: tuple[str, ...],
        input_buffer: BinaryIO,
        opts: tuple[str, ...] | None = None,
    ) -> BinaryIO:
        """Optimize using cwebp and with runtime optional arguments."""
        return self._cwebp(exec_args, input_buffer, opts)
