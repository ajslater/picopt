"""PNG format."""
from typing import Callable, Tuple

from picopt import extern
from picopt.formats.format import (
    ANIMATED_FORMAT_PREFIX,
    CONVERTABLE_LOSSLESS_FORMATS,
    LOSSLESS_FORMAT_PREFIX,
    Format,
)
from picopt.formats.gif import ANIMATED_GIF_FORMATS, GIF_FORMATS
from picopt.formats.png import PNG_CONVERTABLE_FORMATS, PNG_FORMATS
from picopt.pillow.webp_lossless import is_lossless


WEBP_FORMAT = "WEBP"
WEBP_FORMATS = set((WEBP_FORMAT,))
ANIMATED_WEBP_FORMAT = ANIMATED_FORMAT_PREFIX + WEBP_FORMAT
LOSSLESS_WEBP_FORMAT = LOSSLESS_FORMAT_PREFIX + WEBP_FORMAT
WEBP_CONVERTABLE_FORMATS = (
    PNG_CONVERTABLE_FORMATS | PNG_FORMATS | set((LOSSLESS_WEBP_FORMAT,))
)
WEBP_ANIMATED_CONVERTABLE_FORMATS = ANIMATED_GIF_FORMATS
_CWEBP_BASE_ARGS = [
    "cwebp",
    "-mt",
    "-quiet",
    "-sharp_yuv",
    "-af",
    "-alpha_filter",
    "best",
]
_CWEBP_LOSSY_ARGS = _CWEBP_BASE_ARGS + [
    "-m",
    "6",
    "-pass",
    "10",
]
_CWEBP_LOSSLESS_ARGS = _CWEBP_BASE_ARGS + [
    "-lossless",
    "-z",
    "9",
]

_GIF2WEBP_ARGS = [
    "gif2webp",
    "-mixed",
    "-min_size",
    "-m",
    "6",
    "-mt",
]


class WebP(Format):
    """WebP format class."""

    CONVERTABLE_FORMATS: set = (
        CONVERTABLE_LOSSLESS_FORMATS
        | GIF_FORMATS
        | PNG_FORMATS
        | set([LOSSLESS_WEBP_FORMAT])
    )
    OUT_EXT: str = "." + WEBP_FORMAT.lower()
    BEST_ONLY: bool = True

    @staticmethod
    def cwebp(ext_args: extern.ExtArgs) -> str:
        """Determine webp type and dispatch to handler."""
        image_format = ext_args.image_format
        if image_format == WEBP_FORMAT and is_lossless(ext_args.old_fn):
            image_format = LOSSLESS_WEBP_FORMAT

        if image_format in WebP.CONVERTABLE_FORMATS:
            args_prefix = _CWEBP_LOSSLESS_ARGS
        else:
            args_prefix = _CWEBP_LOSSY_ARGS

        args = tuple(args_prefix + [ext_args.old_fn, "-o", ext_args.new_fn])
        extern.run_ext(args)

        return WEBP_FORMAT

    PROGRAMS: Tuple[Callable[[extern.ExtArgs], str], ...] = (cwebp,)


class AnimatedWebP(Format):
    """
    Animated WebP format class.

    There are no easy animated WebP optimization tools. So this only
    converts animated gifs.
    """

    CONVERTABLE_FORMATS = WEBP_ANIMATED_CONVERTABLE_FORMATS
    OUT_EXT = "." + WEBP_FORMAT.lower()

    @staticmethod
    def gif2webp(ext_args: extern.ExtArgs) -> str:
        """Convert animated gif to animated webp."""
        if ext_args.image_format not in AnimatedWebP.CONVERTABLE_FORMATS:
            raise Exception(f"Wrong format for gif2webp: {ext_args.image_format}")
        args = tuple(_GIF2WEBP_ARGS + [ext_args.old_fn, "-o", ext_args.new_fn])
        extern.run_ext(args)

        return ANIMATED_WEBP_FORMAT

    PROGRAMS: Tuple[Callable[[extern.ExtArgs], str], ...] = (gif2webp,)
