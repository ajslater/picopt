"""PNG format."""
from typing import Callable, Tuple

from picopt import extern
from picopt.formats.format import CONVERTABLE_LOSSLESS_FORMATS, Format
from picopt.formats.gif import GIF_FORMAT
from picopt.pillow.png_bit_depth import png_bit_depth


PNG_FORMAT = "PNG"
PNG_FORMATS = set((PNG_FORMAT,))
PNG_CONVERTABLE_FORMATS = (
    CONVERTABLE_LOSSLESS_FORMATS | set((GIF_FORMAT,)) | PNG_FORMATS
)
_OPTIPNG_ARGS = ["optipng", "-o6", "-fix", "-force", "-quiet"]
_PNGOUT_ARGS = ["pngout", "-q", "-force", "-y"]


class Png(Format):
    """PNG format class."""

    OUT_EXT = "." + PNG_FORMAT.lower()
    BEST_ONLY = False

    @staticmethod
    def optipng(ext_args: extern.ExtArgs) -> str:
        """Run the external program optipng on the file."""
        args = tuple(_OPTIPNG_ARGS + [ext_args.new_fn])
        extern.run_ext(args)
        return PNG_FORMAT

    @staticmethod
    def pngout(ext_args: extern.ExtArgs) -> str:
        """Run the external program pngout on the file."""
        # if png_bit_depth(ext_args.old_fn) == 16:
        depth = png_bit_depth(ext_args.old_fn)
        if depth in (16, None):
            print(f"Skipped pngout for {depth} bit PNG:")
        else:
            args = tuple(_PNGOUT_ARGS + [ext_args.old_fn, ext_args.new_fn])
            extern.run_ext(args)
        return PNG_FORMAT

    PROGRAMS: Tuple[Callable[[extern.ExtArgs], str], ...] = (
        optipng,
        pngout,
    )
