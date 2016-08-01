"""PNG format."""
from .. import extern

FORMATS = set(['PNG'])
LOSSLESS_FORMATS = set(('PNM', 'PPM', 'TIFF', 'BMP', 'GIF'))
CONVERTABLE_FORMATS = LOSSLESS_FORMATS | FORMATS

OPTIPNG_ARGS = ['optipng', '-o6', '-fix', '-preserve', '-force', '-quiet']
ADVPNG_ARGS = ['advpng', '-z', '-4', '-f']
PNGOUT_ARGS = ['pngout', '-q', '-force', '-y']


def optipng(ext_args):
    """Run the externAL program optipng on the file."""
    args = OPTIPNG_ARGS + [ext_args.new_filename]
    extern.run_ext(args)


def advpng(ext_args):
    """Run the externAL program advpng on the file."""
    args = ADVPNG_ARGS + [ext_args.new_filename]
    extern.run_ext(args)


def pngout(ext_args):
    """Run the externAL program pngout on the file."""
    args = PNGOUT_ARGS + [ext_args.old_filename, ext_args.new_filename]
    extern.run_ext(args)


PROGRAMS = (optipng, advpng, pngout)
BEST_ONLY = False
