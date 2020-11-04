"""All the default formats."""
from typing import Set

from picopt.formats.comic import Comic
from picopt.formats.gif import Gif
from picopt.formats.jpeg import Jpeg
from picopt.formats.png import Png


ALL_DEFAULT_FORMATS: Set[str] = Jpeg.FORMATS | Gif.FORMATS | Png.CONVERTABLE_FORMATS
ALL_FORMATS: Set[str] = ALL_DEFAULT_FORMATS | Comic.FORMATS
