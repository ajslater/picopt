"""JPEG format."""
import copy

from typing import Callable, Tuple

from picopt import extern
from picopt.formats.format import Format


JPEG_FORMAT = "JPEG"
JPEG_FORMATS = set((JPEG_FORMAT,))
_JPEGTRAN_ARGS = ["-optimize", "-progressive"]


class Jpeg(Format):
    """JPEG format class."""

    BEST_ONLY = True
    OUT_EXT = ".jpg"

    @staticmethod
    def _jpegtran(exe: str, ext_args: extern.ExtArgs) -> str:
        """Run the jpegtran type program."""
        args = [exe] + copy.copy(_JPEGTRAN_ARGS)
        if ext_args.destroy_metadata:
            args += ["-copy", "none"]
        else:
            args += ["-copy", "all"]
        args += ["-outfile"]
        args += [ext_args.new_fn, ext_args.old_fn]
        extern.run_ext(tuple(args))
        return JPEG_FORMAT

    @staticmethod
    def mozjpeg(ext_args: extern.ExtArgs) -> str:
        """Create argument list for mozjpeg."""
        return Jpeg._jpegtran("mozjpeg", ext_args)

    @staticmethod
    def jpegtran(ext_args: extern.ExtArgs) -> str:
        """Create argument list for jpegtran."""
        return Jpeg._jpegtran("jpegtran", ext_args)

    PROGRAMS: Tuple[Callable[[extern.ExtArgs], str], ...] = (
        mozjpeg,
        jpegtran,
    )
