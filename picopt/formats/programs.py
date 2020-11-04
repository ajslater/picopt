"""A list of all the programs."""
from picopt.formats.gif import Gif
from picopt.formats.jpeg import Jpeg
from picopt.formats.png import Png


PROGRAMS = Png.PROGRAMS + Gif.PROGRAMS + Jpeg.PROGRAMS
