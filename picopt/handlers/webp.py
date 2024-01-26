"""WebP format."""
from abc import ABC
from pathlib import Path
from types import MappingProxyType

from PIL.WebPImagePlugin import WebPImageFile

from picopt.handlers.convertible import TIFF_FILE_FORMAT
from picopt.handlers.handler import FileFormat
from picopt.handlers.image import ImageHandler
from picopt.handlers.png import Png


class WebPBase(ImageHandler, ABC):
    """Base for handlers that use WebP utility commands."""

    PIL2_KWARGS = MappingProxyType({"quality": 100, "method": 6})
    OUTPUT_FORMAT_STR = WebPImageFile.format
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

    def cwebp(self, exec_args: tuple[str, ...], old_path: Path, new_path: Path) -> Path:
        """Optimize using cwebp."""
        args = [*exec_args, *self.CWEBP_ARGS_PREFIX]
        args += ["-metadata"]
        if self.config.keep_metadata:
            args += ["all"]
        else:
            args += ["none"]
        args += [str(old_path), "-o", str(new_path)]
        self.run_ext(tuple(args))
        return new_path


class WebPLossless(WebPBase):
    """Handle lossless webp images and images that convert to lossless webp."""

    OUTPUT_FILE_FORMAT = FileFormat(WebPBase.OUTPUT_FORMAT_STR, True, False)
    INPUT_FILE_FORMATS = frozenset(
        {OUTPUT_FILE_FORMAT, Png.OUTPUT_FILE_FORMAT, TIFF_FILE_FORMAT}
    )
    CONVERT_FROM_FORMAT_STRS = frozenset(
        Png.CONVERT_FROM_FORMAT_STRS | {Png.OUTPUT_FORMAT_STR}
    )
    CWEBP_ARGS_PREFIX = (
        # https://groups.google.com/a/webmproject.org/g/webp-discuss/c/0GmxDmlexek
        "-near_lossless",
        "0",
        *WebPBase.CWEBP_ARGS_PREFIX,
    )
    PIL2_KWARGS = MappingProxyType({**WebPBase.PIL2_KWARGS, "lossless": True})
    CONVERGEABLE = frozenset({"cwebp"})
    PROGRAMS = (("pil2png",), ("cwebp", "pil2native"))
