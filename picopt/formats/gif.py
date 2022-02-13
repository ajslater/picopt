"""Gif format."""
from typing import Callable, Tuple

from picopt import extern
from picopt.extern import ExtArgs
from picopt.formats.format import ANIMATED_FORMAT_PREFIX, Format


GIF_FORMAT = "GIF"
ANIMATED_GIF_FORMAT = ANIMATED_FORMAT_PREFIX + GIF_FORMAT
ANIMATED_GIF_FORMATS = set((ANIMATED_GIF_FORMAT,))
GIF_FORMATS = set((GIF_FORMAT, ANIMATED_GIF_FORMAT))
_GIFSICLE_ARGS = ["gifsicle", "--optimize=3", "--batch"]


class Gif(Format):
    """GIF format class."""

    BEST_ONLY = True
    OUT_EXT = "." + GIF_FORMAT.lower()

    @staticmethod
    def gifsicle(ext_args: ExtArgs) -> str:
        """Run the EXTERNAL program gifsicle."""
        args = tuple(_GIFSICLE_ARGS + [ext_args.new_fn])
        extern.run_ext(args)
        return GIF_FORMAT

    PROGRAMS: Tuple[Callable[[ExtArgs], str], ...] = (gifsicle,)
