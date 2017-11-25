"""JPEG format."""
from __future__ import absolute_import, division, print_function

import copy

from .. import extern
from ..settings import Settings

_JPEG_FORMAT = 'JPEG'
FORMATS = set([_JPEG_FORMAT])
OUT_EXT = '.jpg'

_MOZJPEG_ARGS = ['mozjpeg']
_JPEGTRAN_ARGS = ['jpegtran', '-optimize']
_JPEGRESCAN_ARGS = ['jpegrescan']


def mozjpeg(ext_args):
    """Create argument list for mozjpeg."""
    args = copy.copy(_MOZJPEG_ARGS)
    if Settings.destroy_metadata:
        args += ["-copy", "none"]
    else:
        args += ["-copy", "all"]
    args += ['-outfile']
    args += [ext_args.new_filename, ext_args.old_filename]
    extern.run_ext(args)
    return _JPEG_FORMAT


def jpegtran(ext_args):
    """Create argument list for jpegtran."""
    args = copy.copy(_JPEGTRAN_ARGS)
    if Settings.destroy_metadata:
        args += ["-copy", "none"]
    else:
        args += ["-copy", "all"]
    if Settings.jpegtran_prog:
        args += ["-progressive"]
    args += ['-outfile']
    args += [ext_args.new_filename, ext_args.old_filename]
    extern.run_ext(args)
    return _JPEG_FORMAT


def jpegrescan(ext_args):
    """Run the EXTERNAL program jpegrescan."""
    args = copy.copy(_JPEGRESCAN_ARGS)
    if Settings.jpegrescan_multithread:
        args += ['-t']
    if Settings.destroy_metadata:
        args += ['-s']
    args += [ext_args.old_filename, ext_args.new_filename]
    extern.run_ext(args)
    return _JPEG_FORMAT


PROGRAMS = (mozjpeg, jpegrescan, jpegtran)
BEST_ONLY = True
