"""PNG format."""
from .. import extern
from .png_bit_depth import png_bit_depth

_PNG_FORMAT = 'PNG'
FORMATS = set([_PNG_FORMAT])
LOSSLESS_FORMATS = set(('PNM', 'PPM', 'BMP', 'GIF'))
CONVERTABLE_FORMATS = LOSSLESS_FORMATS | FORMATS
OUT_EXT = '.'+_PNG_FORMAT.lower()

_OPTIPNG_ARGS = ['optipng', '-o6', '-fix', '-preserve', '-force', '-quiet']
_ADVPNG_ARGS = ['advpng', '-z', '-4', '-f']
_PNGOUT_ARGS = ['pngout', '-q', '-force', '-y']


def optipng(ext_args):
    """Run the external program optipng on the file."""
    args = _OPTIPNG_ARGS + [ext_args.new_fn]
    extern.run_ext(args)
    return _PNG_FORMAT


def advpng(ext_args):
    """Run the external program advpng on the file."""
    args = _ADVPNG_ARGS + [ext_args.new_fn]
    extern.run_ext(args)
    return _PNG_FORMAT


def pngout(ext_args):
    """Run the external program pngout on the file."""
    # if png_bit_depth(ext_args.old_fn) == 16:
    depth = png_bit_depth(ext_args.old_fn)
    if depth in (16, None):
        print(f'Skipped pngout for {depth} bit PNG:')
    else:
        args = _PNGOUT_ARGS + [ext_args.old_fn, ext_args.new_fn]
        extern.run_ext(args)
    return _PNG_FORMAT


PROGRAMS = (optipng, advpng, pngout)
BEST_ONLY = False
