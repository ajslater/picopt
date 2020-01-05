#!/usr/bin/env python3
"""Run pictures through image specific external optimizers."""
import argparse
import time
from argparse import Namespace
from pathlib import Path
from typing import Callable, Set, Tuple

import dateutil.parser
import pkg_resources

from . import PROGRAM_NAME, walk
from .extern import ExtArgs
from .formats.comic import Comic
from .formats.gif import Gif
from .formats.jpeg import Jpeg
from .formats.png import Png
from .settings import Settings

DISTRIBUTION = pkg_resources.get_distribution(PROGRAM_NAME)
PROGRAMS: Set[Callable[[ExtArgs], str]] = set(Png.PROGRAMS +
                                              Gif.PROGRAMS +
                                              Jpeg.PROGRAMS)

FORMAT_DELIMETER = ','
DEFAULT_FORMATS = 'ALL'
ALL_DEFAULT_FORMATS: Set[str] = Jpeg.FORMATS | Gif.FORMATS | \
                                Png.CONVERTABLE_FORMATS
ALL_FORMATS: Set[str] = ALL_DEFAULT_FORMATS | Comic.FORMATS


def get_arguments(args: Tuple[str, ...]) -> Namespace:
    """Parse the command line."""
    usage = "%(prog)s [arguments] [image files]"
    programs_str = ', '.join(
        (prog.__func__.__name__ for prog in PROGRAMS))  # type: ignore
    description = f"Uses {programs_str} if they are on the path."
    parser = argparse.ArgumentParser(usage=usage, description=description)
    all_formats = ', '.join(sorted(ALL_FORMATS))
    lossless_formats = ', '.join(Png.LOSSLESS_FORMATS)
    parser.add_argument("-r", "--recurse", action="store_true",
                        dest="recurse", default=0,
                        help="Recurse down through directories ignoring the"
                        "image file arguments on the command line")
    parser.add_argument("-v", "--verbose", action="count",
                        dest="verbose", default=0,
                        help="Display more output. -v (default) and -vv "
                        "(noisy)")
    parser.add_argument("-Q", "--quiet", action="store_const",
                        dest="verbose", const=-1,
                        help="Display little to no output")
    parser.add_argument("-a", "--enable_advpng", action="store_true",
                        dest="advpng", default=0,
                        help="Optimize with advpng (disabled by default)")
    parser.add_argument("-c", "--comics", action="store_true",
                        dest="comics", default=0,
                        help="Also optimize comic book archives (cbz & cbr)")
    parser.add_argument("-f", "--formats", action="store", dest="formats",
                        default=DEFAULT_FORMATS,
                        help="Only optimize images of the specifed"
                        f"'{FORMAT_DELIMETER}' delimited formats from:"
                        f" {all_formats}")
    parser.add_argument("-O", "--disable_optipng", action="store_false",
                        dest="optipng", default=1,
                        help="Do not optimize with optipng")
    parser.add_argument("-P", "--disable_pngout", action="store_false",
                        dest="pngout", default=1,
                        help="Do not optimize with pngout")
    parser.add_argument("-J", "--disable_jpegrescan", action="store_false",
                        dest="jpegrescan", default=1,
                        help="Do not optimize with jpegrescan")
    parser.add_argument("-E", "--disable_progressive", action="store_false",
                        dest="jpegtran_prog", default=1,
                        help="Don't try to reduce size by making "
                        "progressive JPEGs with jpegtran")
    parser.add_argument("-Z", "--disable_mozjpeg", action="store_false",
                        dest="mozjpeg", default=1,
                        help="Do not optimize with mozjpeg")
    parser.add_argument("-T", "--disable_jpegtran", action="store_false",
                        dest="jpegtran", default=1,
                        help="Do not optimize with jpegtran")
    parser.add_argument("-G", "--disable_gifsicle", action="store_false",
                        dest="gifsicle", default=1,
                        help="disable optimizing animated GIFs")
    parser.add_argument("-Y", "--disable_convert_type", action="store_const",
                        dest="to_png_formats",
                        const=Png.FORMATS,
                        default=Png.CONVERTABLE_FORMATS,
                        help="Do not convert other lossless formats"
                        f"like {lossless_formats} to PNG when "
                        f"optimizing. By default, {PROGRAM_NAME}"
                        " does convert these formats to PNG")
    parser.add_argument("-S", "--disable_follow_symlinks",
                        action="store_false",
                        dest="follow_symlinks", default=1,
                        help="disable following symlinks for files and "
                        "directories")
    parser.add_argument("-b", "--bigger", action="store_true",
                        dest="bigger", default=0,
                        help="Save optimized files that are larger than "
                        "the originals")
    parser.add_argument("-t", "--record_timestamp", action="store_true",
                        dest="record_timestamp", default=0,
                        help="Store the time of the optimization of full "
                        "directories in directory local dotfiles.")
    parser.add_argument("-D", "--optimize_after", action="store",
                        dest="optimize_after", default=None,
                        help="only optimize files after the specified "
                        "timestamp. Supercedes .picopt_timestamp file.")
    parser.add_argument("-N", "--noop", action="store_true",
                        dest="test", default=0,
                        help="Do not replace files with optimized versions")
    parser.add_argument("-l", "--list", action="store_true",
                        dest="list_only", default=0,
                        help="Only list files that would be optimized")
    parser.add_argument("-V", "--version", action="version",
                        version=DISTRIBUTION.version,
                        help="Display the version number")
    parser.add_argument("-M", "--destroy_metadata", action="store_true",
                        dest="destroy_metadata", default=0,
                        help="*Destroy* metadata like EXIF and JFIF")
    parser.add_argument("paths", metavar="path", type=str, nargs="+",
                        help="File or directory paths to optimize")
    parser.add_argument("-j", "--jobs", type=int, action="store",
                        dest="jobs", default=0,
                        help="Number of parallel jobs to run simultaneously.")

    return parser.parse_args(args[1:])


def process_arguments(arguments: Namespace) -> None:
    """
    Recompute special cases for input arguments.

    Sets the global Settings singleton with the correct values from arguments.
    """
    Settings.update(arguments)

    Settings.config_program_reqs(PROGRAMS)

    Settings.verbose = arguments.verbose + 1
    Settings.paths = set(arguments.paths)

    if arguments.formats == DEFAULT_FORMATS:
        Settings.formats = arguments.to_png_formats | \
            Jpeg.FORMATS | Gif.FORMATS
    else:
        Settings.formats = set(
            arguments.formats.upper().split(FORMAT_DELIMETER))

    if arguments.comics:
        Settings.formats = Settings.formats | Comic.FORMATS

    if Settings.verbose >= 0 or arguments.formats != DEFAULT_FORMATS:
        print("Optimizing formats:", *Settings.formats)

    if arguments.optimize_after is not None:
        try:
            after_dt = dateutil.parser.parse(arguments.optimize_after)
            if Settings.verbose >= 0:
                print('Optimizing after', after_dt)
            Settings.optimize_after = time.mktime(after_dt.timetuple())
        except Exception as ex:
            print(ex)
            print('Could not parse date to optimize after.')
            exit(1)

    if arguments.jobs < 1:
        Settings.jobs = 1

    # Make a rough guess about weather or not to invoke multithreding
    # jpegrescan '-t' uses three threads
    # one off multithread switch because this is the only one right now
    files_in_paths = 0
    non_file_in_paths = False
    for filename in arguments.paths:
        path = Path(filename)
        if path.is_file():
            files_in_paths += 1

        elif path.exists():
            non_file_in_paths = True
        else:
            print(f"'{filename}' does not exist.")
            exit(1)

    Settings.jpegrescan_multithread = not non_file_in_paths and \
        Settings.jobs - (files_in_paths*3) > -1


def run(args: Tuple[str, ...]) -> bool:
    """Process command line arguments and walk inputs."""
    raw_arguments = get_arguments(args)
    process_arguments(raw_arguments)
    walk.run()
    return True


def main() -> None:
    """CLI entry point."""
    import sys
    run(tuple(sys.argv))


if __name__ == '__main__':
    main()
