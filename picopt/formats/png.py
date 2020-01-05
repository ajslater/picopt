"""PNG format."""
from .. import extern
from .format import Format
from .png_bit_depth import png_bit_depth

_PNG_FORMAT = 'PNG'
_OPTIPNG_ARGS = ['optipng', '-o6', '-fix', '-preserve', '-force', '-quiet']
_ADVPNG_ARGS = ['advpng', '-z', '-4', '-f']
_PNGOUT_ARGS = ['pngout', '-q', '-force', '-y']


class Png(Format):
    """PNG format class."""

    FORMATS = set([_PNG_FORMAT])
    LOSSLESS_FORMATS = set(('PNM', 'PPM', 'BMP', 'GIF'))
    CONVERTABLE_FORMATS = LOSSLESS_FORMATS | FORMATS
    OUT_EXT = '.'+_PNG_FORMAT.lower()
    BEST_ONLY = False

    @staticmethod
    def optipng(ext_args: extern.ExtArgs) -> str:
        """Run the external program optipng on the file."""
        args = tuple(_OPTIPNG_ARGS + [ext_args.new_fn])
        extern.run_ext(args)
        return _PNG_FORMAT

    @staticmethod
    def advpng(ext_args: extern.ExtArgs) -> str:
        """Run the external program advpng on the file."""
        args = tuple(_ADVPNG_ARGS + [ext_args.new_fn])
        extern.run_ext(args)
        return _PNG_FORMAT

    @staticmethod
    def pngout(ext_args: extern.ExtArgs) -> str:
        """Run the external program pngout on the file."""
        # if png_bit_depth(ext_args.old_fn) == 16:
        depth = png_bit_depth(ext_args.old_fn)
        if depth in (16, None):
            print(f'Skipped pngout for {depth} bit PNG:')
        else:
            args = tuple(_PNGOUT_ARGS + [ext_args.old_fn, ext_args.new_fn])
            extern.run_ext(args)
        return _PNG_FORMAT

    PROGRAMS = (optipng, advpng, pngout)
