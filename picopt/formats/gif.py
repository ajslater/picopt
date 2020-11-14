"""Gif format."""
from typing import Callable
from typing import Tuple

from picopt import extern
from picopt.extern import ExtArgs
from picopt.formats.format import ANIMATED_FORMAT_PREFIX
from picopt.formats.format import Format
from picopt.settings import Settings


_GIF_FORMAT = "GIF"
_ANIMATED_GIF_FORMAT = ANIMATED_FORMAT_PREFIX + _GIF_FORMAT
_GIFSICLE_ARGS = ["gifsicle", "--optimize=3", "--batch"]


class Gif(Format):
    """GIF format class."""

    FORMATS = set([_GIF_FORMAT, _ANIMATED_GIF_FORMAT])
    BEST_ONLY = True
    OUT_EXT = "." + _GIF_FORMAT.lower()

    @staticmethod
    def gifsicle(_: Settings, ext_args: ExtArgs) -> str:
        """Run the EXTERNAL program gifsicle."""
        args = tuple(_GIFSICLE_ARGS + [ext_args.new_fn])
        extern.run_ext(args)
        return _GIF_FORMAT

    PROGRAMS: Tuple[Callable[[Settings, ExtArgs], str], ...] = (gifsicle,)
