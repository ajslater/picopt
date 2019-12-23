"""Format Superclass."""
from typing import Callable, Set, Tuple

from ..extern import ExtArgs


class Format(object):
    PROGRAMS: Tuple[Callable[[ExtArgs], str], ...] = tuple()
    BEST_ONLY: bool = True
    FORMATS: Set[str] = set()
    OUT_EXT: str = 'xxx'
