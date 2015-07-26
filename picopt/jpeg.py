import copy

import extern

PROGRAMS = ['mozjpeg', 'jpegrescan', 'jpegtran']
FORMATS = set(['JPEG'])
MOZJPEG_ARGS = ['mozjpeg']
JPEGTRAN_ARGS = ['jpegtran', '-optimize']
JPEGRESCAN_ARGS = ['jpegrescan']


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


PROG_MAP = (mozjpeg, jpegrescan, jpegtran)


def optimize(filename, arguments):
    """run EXTERNAL programs to optimize jpeg formats"""
    return extern.optimize_with_progs(PROG_MAP, filename, 'JPEG', True,
                                      arguments)
