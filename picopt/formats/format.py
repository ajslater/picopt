"""Format Superclass."""
from typing import Callable, Tuple

from picopt.extern import ExtArgs


ANIMATED_FORMAT_PREFIX: str = "ANIMATED_"
LOSSLESS_FORMAT_PREFIX: str = "LOSSLESS_"
CONVERTABLE_LOSSLESS_FORMATS = set(("PNM", "PPM", "BMP"))


class Format:
    """Format superclass."""

    PROGRAMS: Tuple[Callable[[ExtArgs], str], ...] = tuple()
    BEST_ONLY: bool = True
    OUT_EXT: str = "undefined"
