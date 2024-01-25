"""WebP Animated images are treated like containers."""
from types import MappingProxyType

from picopt.handlers.convertible import (
    CONVERTABLE_ANIMATED_FORMAT_STRS,
    GIF_FORMAT_STR,
    PNG_FORMAT_STR,
)
from picopt.handlers.handler import FileFormat
from picopt.handlers.image import ImageHandler
from picopt.handlers.webp import WebPBase


# TODO move into webp.py
class WebPAnimatedBase(ImageHandler):
    """Animated WebP container."""

    OUTPUT_FORMAT_STR: str = WebPBase.OUTPUT_FORMAT_STR
    PROGRAMS = (("pil2native",),)
    PIL2_ARGS = MappingProxyType({"quality": 100, "method": 6, "minimize_size": True})
    # TODO REMOVE too much trouble to keep metadata
    # _IMG2WEBP_ARGS_PREFIX = ("-min_size", "-lossless", "-q", "100", "-m", "6")


class WebPAnimatedLossless(WebPAnimatedBase):
    """Animated Lossless WebP Handler."""

    OUTPUT_FILE_FORMAT = FileFormat(WebPAnimatedBase.OUTPUT_FORMAT_STR, True, True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    CONVERT_FROM_FORMAT_STRS = frozenset(
        CONVERTABLE_ANIMATED_FORMAT_STRS | {PNG_FORMAT_STR, GIF_FORMAT_STR}
    )
    CONVERGABLE = True
    PIL2_ARGS = MappingProxyType({**WebPAnimatedBase.PIL2_ARGS, "lossless": True})
