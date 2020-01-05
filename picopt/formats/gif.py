"""Gif format."""
from typing import Callable, Tuple

from .. import extern
from .format import Format

_GIF_FORMAT = 'GIF'
_GIFSICLE_ARGS = ['gifsicle', '--optimize=3', '--batch']


class Gif(Format):
    """GIF format class."""

    SEQUENCED_TEMPLATE = '{} SEQUENCED'
    FORMATS = set([SEQUENCED_TEMPLATE.format(_GIF_FORMAT), _GIF_FORMAT])
    BEST_ONLY = True
    OUT_EXT = '.'+_GIF_FORMAT.lower()

    @staticmethod
    def gifsicle(ext_args: extern.ExtArgs) -> str:
        """Run the EXTERNAL program gifsicle."""
        args = tuple(_GIFSICLE_ARGS + [ext_args.new_fn])
        extern.run_ext(args)
        return _GIF_FORMAT

    PROGRAMS: Tuple[Callable[[extern.ExtArgs], str]] = (gifsicle,)
