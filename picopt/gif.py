import extern
import stats

PROGRAMS = ['gifsicle']
GIFSICLE_ARGS = ['gifsicle', '--optimize=3', '--batch']


SEQUENCED_TEMPLATE = '%s SEQUENCED'
GIF_FORMATS = set([SEQUENCED_TEMPLATE % 'GIF', 'GIF'])


def gifsicle(ext_args):
    """runs the EXTERNAL program gifsicle"""
    args = GIFSICLE_ARGS + [ext_args.new_filename]
    extern.run_ext(args)


def optimize_gif(filename, arguments):
    """run EXTERNAL programs to optimize animated gifs"""
    if arguments.gifsicle:
        report_stats = extern.optimize_image_external(filename, arguments,
                                                      gifsicle)
    else:
        rep = ['Skipping animated GIF: %s' % filename]
        bytes_diff = {'in': 0, 'out': 0}
        report_stats = stats.ReportStats._make([filename, bytes_diff, [rep]])

    return report_stats
