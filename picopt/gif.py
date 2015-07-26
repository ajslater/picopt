import extern
import optimize_image

PROGRAMS = ['gifsicle']
SEQUENCED_TEMPLATE = '%s SEQUENCED'
GIF_FORMAT = 'GIF'
FORMATS = set([SEQUENCED_TEMPLATE % GIF_FORMAT, GIF_FORMAT])

GIFSICLE_ARGS = ['gifsicle', '--optimize=3', '--batch']


def gifsicle(ext_args):
    """runs the EXTERNAL program gifsicle"""
    args = GIFSICLE_ARGS + [ext_args.new_filename]
    extern.run_ext(args)


PROG_MAP = (gifsicle,)


def optimize(filename, arguments):
    """run EXTERNAL programs to optimize animated gifs"""
    return optimize_image.optimize_with_progs(PROG_MAP, filename,
                                              'animated GIF', True, arguments)
