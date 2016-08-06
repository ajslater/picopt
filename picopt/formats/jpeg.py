"""JPEG format."""
import copy

from .. import extern
from ..settings import Settings

JPEG_FORMAT = 'JPEG'
FORMATS = set([JPEG_FORMAT])

MOZJPEG_ARGS = ['mozjpeg']
JPEGTRAN_ARGS = ['jpegtran', '-optimize']
JPEGRESCAN_ARGS = ['jpegrescan']


def mozjpeg(ext_args):
    """Create argument list for mozjpeg."""
    args = copy.copy(MOZJPEG_ARGS)
    if Settings.destroy_metadata:
        args += ["-copy", "none"]
    else:
        args += ["-copy", "all"]
    args += ['-outfile']
    args += [ext_args.new_filename, ext_args.old_filename]
    extern.run_ext(args)
    return JPEG_FORMAT


def jpegtran(ext_args):
    """Create argument list for jpegtran."""
    args = copy.copy(JPEGTRAN_ARGS)
    if Settings.destroy_metadata:
        args += ["-copy", "none"]
    else:
        args += ["-copy", "all"]
    if Settings.jpegtran_prog:
        args += ["-progressive"]
    args += ['-outfile']
    args += [ext_args.new_filename, ext_args.old_filename]
    extern.run_ext(args)
    return JPEG_FORMAT


def jpegrescan(ext_args):
    """Run the EXTERNAL program jpegrescan."""
    args = copy.copy(JPEGRESCAN_ARGS)
    if Settings.jpegrescan_multithread:
        args += ['-t']
    if Settings.destroy_metadata:
        args += ['-s']
    args += [ext_args.old_filename, ext_args.new_filename]
    extern.run_ext(args)
    return JPEG_FORMAT


PROGRAMS = (mozjpeg, jpegrescan, jpegtran)
BEST_ONLY = True
