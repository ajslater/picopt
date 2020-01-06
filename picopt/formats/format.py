"""Format Superclass."""
from typing import Callable
from typing import Set
from typing import Tuple

from ..extern import ExtArgs


class Format(object):
    """Format superclass."""

    PROGRAMS: Tuple[Callable[[ExtArgs], str], ...] = tuple()
    BEST_ONLY: bool = True
    FORMATS: Set[str] = set()
    OUT_EXT: str = "xxx"
