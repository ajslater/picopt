"""WebP Animated images are treated like containers."""
from types import MappingProxyType

from picopt.handlers.convertible import (
    CONVERTABLE_ANIMATED_FILE_FORMATS,
    CONVERTABLE_ANIMATED_FORMAT_STRS,
)
from picopt.handlers.gif import Gif, GifAnimated
from picopt.handlers.handler import FileFormat
from picopt.handlers.image_animated import ImageAnimated
from picopt.handlers.png_animated import PngAnimated
from picopt.handlers.webp import WebPBase


class WebPAnimatedBase(ImageAnimated):
    """Animated WebP container."""

    OUTPUT_FORMAT_STR: str = WebPBase.OUTPUT_FORMAT_STR
    PIL2_ARGS = MappingProxyType({"quality": 100, "method": 6, "minimize_size": True})


class WebPAnimatedLossless(WebPAnimatedBase):
    """Animated Lossless WebP Handler."""

    OUTPUT_FILE_FORMAT = FileFormat(WebPAnimatedBase.OUTPUT_FORMAT_STR, True, True)
    INPUT_FILE_FORMATS = frozenset(
        {
            OUTPUT_FILE_FORMAT,
            GifAnimated.OUTPUT_FILE_FORMAT,
            PngAnimated.OUTPUT_FILE_FORMAT,
        }
        | CONVERTABLE_ANIMATED_FILE_FORMATS,
    )
    CONVERT_FROM_FORMAT_STRS = frozenset(
        CONVERTABLE_ANIMATED_FORMAT_STRS
        | {Gif.OUTPUT_FORMAT_STR, PngAnimated.OUTPUT_FORMAT_STR}
    )
    PIL2_ARGS = MappingProxyType({**WebPAnimatedBase.PIL2_ARGS, "lossless": True})
