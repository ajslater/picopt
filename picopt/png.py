import os

import extern
from extern import optimize_image_external
import stats


PROGRAMS = ['optipng', 'pngout', 'advpng']
OPTIPNG_ARGS = ['optipng', '-o6', '-fix', '-preserve', '-force', '-quiet']
ADVPNG_ARGS = ['advpng', '-z', '-4', '-f']
PNGOUT_ARGS = ['pngout', '-q', '-force', '-y']

PNG_FORMATS = set(['PNG'])
LOSSLESS_FORMATS = set(('PNM', 'PPM', 'TIFF', 'BMP', 'GIF'))
PNG_CONVERTABLE_FORMATS = LOSSLESS_FORMATS | PNG_FORMATS


def pngout(ext_args):
    """runs the EXTERNAL program pngout on the file"""
    args = PNGOUT_ARGS + [ext_args.old_filename, ext_args.new_filename]
    extern.run_ext(args)


def optipng(ext_args):
    """runs the EXTERNAL program optipng on the file"""
    args = OPTIPNG_ARGS + [ext_args.new_filename]
    extern.run_ext(args)


def advpng(ext_args):
    """runs the EXTERNAL program advpng on the file"""
    args = ADVPNG_ARGS + [ext_args.new_filename]
    extern.run_ext(args)


def optimize_png(filename, arguments):
    """run EXTERNAL programs to optimize lossless formats to PNGs"""
    filesize_in = os.stat(filename).st_size
    report_stats = None

    for ext_prog in ('optipng', 'advpng', 'pngout'):
        if not getattr(arguments, ext_prog):
            continue
        report_stats = optimize_image_external(filename,
                                               arguments,
                                               globals()[ext_prog])
        filename = report_stats.final_filename

    if report_stats is not None:
        report_stats.bytes_diff['in'] = filesize_in
    else:
        bytes_diff = {'in': 0, 'out': 0}
        rep = 'Skipping file: %s' % filename
        report_stats = stats.ReportStats._make([filename, bytes_diff, rep])

    return report_stats
