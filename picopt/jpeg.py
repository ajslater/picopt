import copy

import extern
from extern import optimize_image_external
import stats

PROGRAMS = ['mozjpeg', 'jpegrescan', 'jpegtran']
MOZJPEG_ARGS = ['mozjpeg']
JPEGTRAN_ARGS = ['jpegtran', '-optimize']
JPEGRESCAN_ARGS = ['jpegrescan']

JPEG_FORMATS = set(['JPEG'])


def mozjpeg(ext_args):
    """create argument list for mozjpeg"""
    args = copy.copy(MOZJPEG_ARGS)
    if ext_args.arguments.destroy_metadata:
        args += ["-copy", "none"]
    else:
        args += ["-copy", "all"]
    args += ['-outfile']
    args += [ext_args.new_filename, ext_args.old_filename]
    extern.run_ext(args)


def jpegtran(ext_args):
    """create argument list for jpegtran"""
    args = copy.copy(JPEGTRAN_ARGS)
    if ext_args.arguments.destroy_metadata:
        args += ["-copy", "none"]
    else:
        args += ["-copy", "all"]
    if ext_args.arguments.jpegtran_prog:
        args += ["-progressive"]
    args += ['-outfile']
    args += [ext_args.new_filename, ext_args.old_filename]
    extern.run_ext(args)


def jpegrescan(ext_args):
    """runs the EXTERNAL program jpegrescan"""
    args = copy.copy(JPEGRESCAN_ARGS)
    if ext_args.arguments.jpegrescan_multithread:
        args += ['-t']
    if ext_args.arguments.destroy_metadata:
        args += ['-s']
    args += [ext_args.old_filename, ext_args.new_filename]
    extern.run_ext(args)


def optimize_jpeg(filename, arguments):
    """run EXTERNAL programs to optimize jpeg formats"""
    final_filename = filename
    if arguments.mozjpeg:
        report_stats = optimize_image_external(
            final_filename, arguments, mozjpeg)
    elif arguments.jpegrescan:
        report_stats = optimize_image_external(
            final_filename, arguments, jpegrescan)
    elif arguments.jpegtran_prog or arguments.jpegtran:
        report_stats = optimize_image_external(
            final_filename, arguments, jpegtran)
    else:
        rep = ['Skipping JPEG file: %s' % filename]
        bytes_diff = {'in': 0, 'out': 0}
        report_stats = stats.ReportStats._make([filename, bytes_diff, [rep]])

    return report_stats
