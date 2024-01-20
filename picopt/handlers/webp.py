"""WebP format."""
from abc import ABC
from pathlib import Path
from types import MappingProxyType
from typing import Any

from PIL.WebPImagePlugin import WebPImageFile

from picopt.handlers.convertible import TIFF_FILE_FORMAT
from picopt.handlers.gif import Gif, GifAnimated
from picopt.handlers.handler import FileFormat
from picopt.handlers.image import ImageHandler
from picopt.handlers.png import Png


class WebPBase(ImageHandler, ABC):
    """Base for handlers that use WebP utility commands."""

    PIL2WEBP_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {"lossless": True, "quality": 100, "method": 6}
    )
    PIL2_ARGS: MappingProxyType[str, Any] = PIL2WEBP_KWARGS

    def get_metadata_args(self) -> list[str]:
        """Get webp utility metadata args."""
        args = ["-metadata"]
        if self.config.keep_metadata:
            args += ["all"]
        else:
            args += ["none"]
        return args

    def pil2webp(self, old_path: Path, new_path: Path) -> Path:
        """Pillow webp optimization."""
        return self.pil2native(old_path, new_path)


class WebP(WebPBase, ABC):
    """WebP format class."""

    OUTPUT_FORMAT_STR = WebPImageFile.format
    PROGRAMS: MappingProxyType[
        str, str | tuple[str, ...] | None
    ] = WebPBase.init_programs(("cwebp",))
    # https://developers.google.com/speed/webp/docs/cwebp
    ARGS_PREFIX = (
        PROGRAMS["cwebp"],
        "-near_lossless",
        "0",
        "-q",
        "100",
        "-m",
        "6",
        "-mt",
        # advanced
        "-sharp_yuv",
        # additional
        "-alpha_filter",
        "best",
    )

    def cwebp(self, old_path: Path, new_path: Path) -> Path:
        """Optimize using cwebp."""
        args = (
            *self.ARGS_PREFIX,
            *self.get_metadata_args(),
            *[str(old_path), "-o", str(new_path)],
        )
        self.run_ext(args)
        return new_path


class WebPLossless(WebP):
    """Handle lossless webp images and images that convert to lossless webp."""

    BEST_ONLY: bool = False
    OUTPUT_FILE_FORMAT = FileFormat(WebP.OUTPUT_FORMAT_STR, True, False)
    INPUT_FILE_FORMATS = frozenset(
        {OUTPUT_FILE_FORMAT, Png.OUTPUT_FILE_FORMAT, TIFF_FILE_FORMAT}
    )
    CONVERT_FROM_FORMAT_STRS = frozenset(
        Png.CONVERT_FROM_FORMAT_STRS | {Png.OUTPUT_FORMAT_STR}
    )
    PREFERRED_PROGRAM: str = "cwebp"
    PROGRAMS: MappingProxyType[str, str | tuple[str, ...] | None] = MappingProxyType(
        {
            "pil2png": None,
            **WebP.PROGRAMS,
            "pil2webp": None,
        }
    )
    ARGS_PREFIX = (*WebP.ARGS_PREFIX, "-lossless")
    PIL2_ARGS = MappingProxyType({"compress_level": 0})

    def pil2png(self, old_path: Path, new_path: Path) -> Path:
        """Internally convert unhandled formats to uncompressed png for cwebp."""
        return self.pil2native(old_path, new_path)

# class WebPLossy(WebP):
#    """Handle lossy webp images."""
#
#    OUTPUT_FILE_FORMAT = FileFormat(WebP.OUTPUT_FORMAT_STR, False, False)
#    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT, JPEG.OUTPUT_FILE_FORMAT, TIFF_FILE_FORMAT})
#    ARGS_PREFIX = (*WebP.ARGS_PREFIX, "-pass", "10", "-af")


class Gif2WebP(WebPBase):
    """Animated WebP format class.

    There are no easy animated WebP optimization tools. So this only
    converts animated gifs.
    """

    OUTPUT_FORMAT_STR = WebP.OUTPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(WebP.OUTPUT_FORMAT_STR, True, True)
    INPUT_FILE_FORMATS = frozenset(
        {Gif.OUTPUT_FILE_FORMAT, GifAnimated.OUTPUT_FILE_FORMAT}
    )
    CONVERT_FROM_FORMAT_STRS = frozenset({Gif.OUTPUT_FORMAT_STR})
    PIL2WEBP_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {
            **WebPLossless.PIL2WEBP_KWARGS,
            "minimize_size": True,
        }
    )
    PREFERRED_PROGRAM = "gif2webp"
    PROGRAMS: MappingProxyType[
        str, str | tuple[str, ...] | None
    ] = WebPBase.init_programs(("gif2webp", "pil2webp"))
    _ARGS_PREFIX = (
        PROGRAMS["gif2webp"],
        "-mixed",
        "-min_size",
        "-q",
        "100",
        "-m",
        "6",
        "-mt",
    )

    @classmethod
    def native_input_file_formats(cls):
        """No native formats."""
        # TODO does this really need to be a method?
        return frozenset()

    def gif2webp(self, old_path: Path, new_path: Path) -> Path:
        """Convert animated gif to animated webp."""
        args = (
            *self._ARGS_PREFIX,
            *self.get_metadata_args(),
            *[str(old_path), "-o", str(new_path)],
        )
        self.run_ext(args)
        return new_path
