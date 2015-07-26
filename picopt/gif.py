import extern

PROGRAMS = ['gifsicle']
GIFSICLE_ARGS = ['gifsicle', '--optimize=3', '--batch']


SEQUENCED_TEMPLATE = '%s SEQUENCED'
GIF_FORMATS = set([SEQUENCED_TEMPLATE % 'GIF', 'GIF'])


def gifsicle(ext_args):
    """runs the EXTERNAL program gifsicle"""
    args = GIFSICLE_ARGS + [ext_args.new_filename]
    extern.run_ext(args)


PROG_MAP = (gifsicle,)


def optimize_gif(filename, arguments):
    """run EXTERNAL programs to optimize animated gifs"""
    return extern.optimize_with_progs(PROG_MAP, filename, 'animated GIF',
                                      True, arguments)
