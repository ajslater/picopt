"""WebP Animated images are treated like containers."""
from types import MappingProxyType

from PIL.WebPImagePlugin import WebPImageFile

from picopt.formats import FileFormat
from picopt.handlers.image_animated import ImageAnimated
from picopt.handlers.png_animated import PngAnimated
from picopt.handlers.webp import WebPBase


class WebPAnimatedBase(ImageAnimated):
    """Animated WebP container."""

    OUTPUT_FORMAT_STR: str = WebPBase.OUTPUT_FORMAT_STR
    PIL2_KWARGS = MappingProxyType({**WebPBase.PIL2_KWARGS, "minimize_size": True})
    PIL2_FRAME_KWARGS = MappingProxyType({"format": WebPImageFile.format, "method": 0})


class WebPAnimatedLossless(WebPAnimatedBase):
    """Animated Lossless WebP Handler."""

    OUTPUT_FILE_FORMAT = FileFormat(WebPAnimatedBase.OUTPUT_FORMAT_STR, True, True)
    INPUT_FILE_FORMATS = frozenset(
        {*PngAnimated.INPUT_FILE_FORMATS, OUTPUT_FILE_FORMAT}
    )
    CONVERT_FROM_FORMAT_STRS = frozenset(
        {*PngAnimated.CONVERT_FROM_FORMAT_STRS, PngAnimated.OUTPUT_FORMAT_STR}
    )
    PIL2_FRAME_KWARGS = MappingProxyType(
        {**WebPAnimatedBase.PIL2_FRAME_KWARGS, "lossless": True, "quality": 0}
    )
    PIL2_KWARGS = MappingProxyType({**WebPAnimatedBase.PIL2_KWARGS, "lossless": True})
