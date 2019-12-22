"""JPEG format."""
import copy
from typing import Tuple

from .. import extern
from ..settings import Settings

_JPEG_FORMAT = 'JPEG'
FORMATS = set([_JPEG_FORMAT])
OUT_EXT = '.jpg'

_MOZJPEG_ARGS = ['mozjpeg']
_JPEGTRAN_ARGS = ['jpegtran', '-optimize']
_JPEGRESCAN_ARGS = ['jpegrescan']


def mozjpeg(ext_args: extern.ExtArgs) -> str:
    """Create argument list for mozjpeg."""
    args = copy.copy(_MOZJPEG_ARGS)
    if Settings.destroy_metadata:
        args += ["-copy", "none"]
    else:
        args += ["-copy", "all"]
    args += ['-outfile']
    args += [ext_args.new_fn, ext_args.old_fn]
    extern.run_ext(tuple(args))
    return _JPEG_FORMAT


def jpegtran(ext_args: extern.ExtArgs) -> str:
    """Create argument list for jpegtran."""
    args = copy.copy(_JPEGTRAN_ARGS)
    if Settings.destroy_metadata:
        args += ["-copy", "none"]
    else:
        args += ["-copy", "all"]
    if Settings.jpegtran_prog:
        args += ["-progressive"]
    args += ['-outfile']
    args += [ext_args.new_fn, ext_args.old_fn]
    extern.run_ext(tuple(args))
    return _JPEG_FORMAT


def jpegrescan(ext_args: extern.ExtArgs) -> str:
    """Run the EXTERNAL program jpegrescan."""
    args = copy.copy(_JPEGRESCAN_ARGS)
    if Settings.jpegrescan_multithread:
        args += ['-t']
    if Settings.destroy_metadata:
        args += ['-s']
    args += [ext_args.old_fn, ext_args.new_fn]
    extern.run_ext(tuple(args))
    return _JPEG_FORMAT


PROGRAMS = (mozjpeg, jpegrescan, jpegtran)
BEST_ONLY = True
