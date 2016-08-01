"""Gif format."""
from .. import extern

SEQUENCED_TEMPLATE = '%s SEQUENCED'
GIF_FORMAT = 'GIF'
FORMATS = set([SEQUENCED_TEMPLATE % GIF_FORMAT, GIF_FORMAT])

GIFSICLE_ARGS = ['gifsicle', '--optimize=3', '--batch']


def gifsicle(ext_args):
    """Run the EXTERNAL program gifsicle."""
    args = GIFSICLE_ARGS + [ext_args.new_filename]
    extern.run_ext(args)


PROGRAMS = (gifsicle,)
BEST_ONLY = True
