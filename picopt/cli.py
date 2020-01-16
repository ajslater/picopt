#!/usr/bin/env python3
"""Run pictures through image specific external optimizers."""
import argparse

from argparse import Namespace
from typing import Callable
from typing import Set
from typing import Tuple

import pkg_resources

from . import PROGRAM_NAME
from . import walk
from .extern import ExtArgs
from .formats.comic import Comic
from .formats.gif import Gif
from .formats.jpeg import Jpeg
from .formats.png import Png
from .settings import Settings


FORMAT_DELIMETER = ","
DISTRIBUTION = pkg_resources.get_distribution(PROGRAM_NAME)
PROGRAMS: Set[Callable[[Settings, ExtArgs], str]] = set(
    Png.PROGRAMS + Gif.PROGRAMS + Jpeg.PROGRAMS
)

ALL_DEFAULT_FORMATS: Set[str] = Jpeg.FORMATS | Gif.FORMATS | Png.CONVERTABLE_FORMATS
ALL_FORMATS: Set[str] = ALL_DEFAULT_FORMATS | Comic.FORMATS


def csv_set(csv_str: str) -> Set[str]:
    """Convert csv string from argparse to a list."""
    return set(csv_str.upper().split(FORMAT_DELIMETER))


def get_arguments(args: Tuple[str, ...]) -> Namespace:
    """Parse the command line."""
    usage = "%(prog)s [arguments] [image files]"
    programs_str = ", ".join(
        (prog.__func__.__name__ for prog in PROGRAMS)  # type: ignore
    )
    description = f"Uses {programs_str} if they are on the path."
    parser = argparse.ArgumentParser(usage=usage, description=description)
    all_formats = ", ".join(sorted(ALL_FORMATS))
    lossless_formats = ", ".join(Png.LOSSLESS_FORMATS)
    parser.add_argument(
        "-r",
        "--recurse",
        action="store_true",
        dest="recurse",
        default=0,
        help="Recurse down through directories ignoring the"
        "image file arguments on the command line",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        dest="verbose",
        default=0,
        help="Display more output. -v (default) and -vv " "(noisy)",
    )
    parser.add_argument(
        "-Q",
        "--quiet",
        action="store_const",
        dest="verbose",
        const=-1,
        help="Display little to no output",
    )
    #    parser.add_argument(
    #        "-a",
    #        "--enable_advpng",
    #        action="store_true",
    #        dest="advpng",
    #        default=0,
    #        help="Optimize with advpng (disabled by default)",
    #    )
    parser.add_argument(
        "-c",
        "--comics",
        action="store_true",
        dest="comics",
        default=0,
        help="Also optimize comic book archives (cbz & cbr)",
    )
    parser.add_argument(
        "-f",
        "--formats",
        type=csv_set,
        action="store",
        dest="formats",
        default=set(),
        help="Only optimize images of the specifed"
        f"'{FORMAT_DELIMETER}' delimited formats from:"
        f" {all_formats}",
    )
    parser.add_argument(
        "-O",
        "--disable_optipng",
        action="store_false",
        dest="optipng",
        default=1,
        help="Do not optimize with optipng",
    )
    parser.add_argument(
        "-P",
        "--disable_pngout",
        action="store_false",
        dest="pngout",
        default=1,
        help="Do not optimize with pngout",
    )
    #    parser.add_argument(
    #        "-J",
    #        "--disable_jpegrescan",
    #        action="store_false",
    #        dest="jpegrescan",
    #        default=1,
    #        help="Do not optimize with jpegrescan",
    #    )
    parser.add_argument(
        "-E",
        "--disable_progressive",
        action="store_false",
        dest="jpegtran_prog",
        default=1,
        help="Don't try to reduce size by making " "progressive JPEGs with jpegtran",
    )
    parser.add_argument(
        "-Z",
        "--disable_mozjpeg",
        action="store_false",
        dest="mozjpeg",
        default=1,
        help="Do not optimize with mozjpeg",
    )
    parser.add_argument(
        "-T",
        "--disable_jpegtran",
        action="store_false",
        dest="jpegtran",
        default=1,
        help="Do not optimize with jpegtran",
    )
    parser.add_argument(
        "-G",
        "--disable_gifsicle",
        action="store_false",
        dest="gifsicle",
        default=1,
        help="disable optimizing animated GIFs",
    )
    parser.add_argument(
        "-Y",
        "--disable_convert_type",
        action="store_const",
        dest="to_png_formats",
        const=Png.FORMATS,
        default=Png.CONVERTABLE_FORMATS,
        help="Do not convert other lossless formats"
        f"like {lossless_formats} to PNG when "
        f"optimizing. By default, {PROGRAM_NAME}"
        " does convert these formats to PNG",
    )
    parser.add_argument(
        "-S",
        "--disable_follow_symlinks",
        action="store_false",
        dest="follow_symlinks",
        default=1,
        help="disable following symlinks for files and " "directories",
    )
    parser.add_argument(
        "-b",
        "--bigger",
        action="store_true",
        dest="bigger",
        default=0,
        help="Save optimized files that are larger than " "the originals",
    )
    parser.add_argument(
        "-t",
        "--record_timestamp",
        action="store_true",
        dest="record_timestamp",
        default=0,
        help="Store the time of the optimization of full "
        "directories in directory local dotfiles.",
    )
    parser.add_argument(
        "-D",
        "--optimize_after",
        action="store",
        dest="optimize_after",
        type=Settings.parse_date_string,
        default=None,
        help="only optimize files after the specified "
        "timestamp. Supercedes .picopt_timestamp file.",
    )
    parser.add_argument(
        "-N",
        "--noop",
        action="store_true",
        dest="test",
        default=0,
        help="Do not replace files with optimized versions",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        dest="list_only",
        default=0,
        help="Only list files that would be optimized",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=DISTRIBUTION.version,
        help="Display the version number",
    )
    parser.add_argument(
        "-M",
        "--destroy_metadata",
        action="store_true",
        dest="destroy_metadata",
        default=0,
        help="*Destroy* metadata like EXIF and JFIF",
    )
    parser.add_argument(
        "paths",
        metavar="path",
        type=str,
        nargs="+",
        help="File or directory paths to optimize",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        action="store",
        dest="jobs",
        default=0,
        help="Number of parallel jobs to run simultaneously.",
    )

    return parser.parse_args(args[1:])


def run(args: Tuple[str, ...]) -> bool:
    """Process command line arguments and walk inputs."""
    arguments = get_arguments(args)
    settings = Settings(PROGRAMS, arguments)
    wob = walk.Walk(settings)
    return wob.run()


def main() -> None:
    """CLI entry point."""
    import sys

    res = run(tuple(sys.argv))
    if not res:
        sys.exit(1)


if __name__ == "__main__":
    main()
