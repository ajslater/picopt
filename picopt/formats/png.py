"""PNG format."""
from pathlib import Path
from typing import Callable
from typing import Optional
from typing import Tuple

from .. import extern
from ..settings import Settings
from .format import Format
from .png_bit_depth import png_bit_depth


_PNG_FORMAT = "PNG"
_OPTIPNG_ARGS = ["optipng", "-o6", "-fix", "-force", "-quiet"]
# _ADVPNG_ARGS = ["advpng", "-z", "-4", "-f"]
_PNGOUT_ARGS = ["pngout", "-q", "-force", "-y"]


class Png(Format):
    """PNG format class."""

    FORMATS = set([_PNG_FORMAT])
    LOSSLESS_FORMATS = set(("PNM", "PPM", "BMP", "GIF"))
    CONVERTABLE_FORMATS = LOSSLESS_FORMATS | FORMATS
    OUT_EXT = "." + _PNG_FORMAT.lower()
    BEST_ONLY = False

    @staticmethod
    def optipng(_: Optional[Settings], ext_args: extern.ExtArgs) -> str:
        """Run the external program optipng on the file."""
        args = tuple(_OPTIPNG_ARGS + [ext_args.new_fn])
        extern.run_ext(args)
        return _PNG_FORMAT

    #    @staticmethod
    #    def advpng(_, ext_args: extern.ExtArgs) -> str:
    #        """Run the external program advpng on the file."""
    #        args = tuple(_ADVPNG_ARGS + [ext_args.new_fn])
    #        extern.run_ext(args)
    #        return _PNG_FORMAT

    @staticmethod
    def pngout(_: Optional[Settings], ext_args: extern.ExtArgs) -> str:
        """Run the external program pngout on the file."""
        # if png_bit_depth(ext_args.old_fn) == 16:
        depth = png_bit_depth(Path(ext_args.old_fn))
        if depth in (16, None):
            print(f"Skipped pngout for {depth} bit PNG:")
        else:
            args = tuple(_PNGOUT_ARGS + [ext_args.old_fn, ext_args.new_fn])
            extern.run_ext(args)
        return _PNG_FORMAT

    PROGRAMS: Tuple[Callable[[Settings, extern.ExtArgs], str], ...] = (
        optipng,
        # advpng,
        pngout,
    )
