"""Gif format."""
from .. import extern

SEQUENCED_TEMPLATE = '{} SEQUENCED'
_GIF_FORMAT = 'GIF'
FORMATS = set([SEQUENCED_TEMPLATE.format(_GIF_FORMAT), _GIF_FORMAT])
OUT_EXT = '.'+_GIF_FORMAT.lower()

_GIFSICLE_ARGS = ['gifsicle', '--optimize=3', '--batch']


def gifsicle(ext_args):
    """Run the EXTERNAL program gifsicle."""
    args = _GIFSICLE_ARGS + [ext_args.new_fn]
    extern.run_ext(args)
    return _GIF_FORMAT


PROGRAMS = (gifsicle,)
BEST_ONLY = True
