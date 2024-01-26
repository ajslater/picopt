"""WebP Animated images are treated like containers."""
from picopt.handlers.convertible import (
    CONVERTABLE_ANIMATED_FILE_FORMATS,
    CONVERTABLE_ANIMATED_FORMAT_STRS,
)
from picopt.handlers.gif import Gif, GifAnimated
from picopt.handlers.handler import FileFormat
from picopt.handlers.image_animated import ImageAnimated
from picopt.handlers.png import Png


class PngAnimated(ImageAnimated):
    """Animated Png container."""

    OUTPUT_FORMAT_STR: str = Png.OUTPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, True, True)
    INPUT_FILE_FORMATS = frozenset(
        {OUTPUT_FILE_FORMAT, GifAnimated.OUTPUT_FILE_FORMAT}
        | CONVERTABLE_ANIMATED_FILE_FORMATS,
    )
    CONVERT_FROM_FORMAT_STRS = frozenset(
        CONVERTABLE_ANIMATED_FORMAT_STRS | {Gif.OUTPUT_FORMAT_STR}
    )
    PIL2_KWARGS = Png.PIL2_KWARGS
