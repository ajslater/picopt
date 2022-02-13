#!/usr/bin/env python3
"""Run pictures through image specific external optimizers."""
import argparse

from argparse import Namespace
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional, Set, Tuple

from picopt import PROGRAM_NAME, walk
from picopt.formats.comic_formats import COMIC_FORMATS
from picopt.formats.format import CONVERTABLE_LOSSLESS_FORMATS
from picopt.formats.gif import GIF_FORMATS
from picopt.formats.jpeg import JPEG_FORMATS
from picopt.formats.png import PNG_CONVERTABLE_FORMATS, PNG_FORMATS
from picopt.formats.webp import (
    WEBP_ANIMATED_CONVERTABLE_FORMATS,
    WEBP_CONVERTABLE_FORMATS,
    WEBP_FORMATS,
)
from picopt.settings import Settings
from picopt.timestamp import Timestamp


FORMAT_DELIMETER = ","
try:
    VERSION = version(PROGRAM_NAME)
except PackageNotFoundError:
    VERSION = "test"
ALL_FORMATS: Set[str] = (
    JPEG_FORMATS
    | GIF_FORMATS
    | CONVERTABLE_LOSSLESS_FORMATS
    | PNG_FORMATS
    | WEBP_FORMATS
    | COMIC_FORMATS
)


def csv_set(csv_str: str) -> Set[str]:
    """Convert csv string from argparse to a list."""
    return set(csv_str.upper().split(FORMAT_DELIMETER))


def get_arguments(args: Tuple[str, ...]) -> Namespace:
    """Parse the command line."""
    usage = "%(prog)s [arguments] [paths]"
    description = "Losslessly optimizes and optionally converts images."
    parser = argparse.ArgumentParser(usage=usage, description=description)
    all_formats = ", ".join(sorted(ALL_FORMATS))
    png_lossless_formats = ", ".join(sorted(PNG_CONVERTABLE_FORMATS))
    webp_lossless_formats = ", ".join(sorted(WEBP_CONVERTABLE_FORMATS))
    parser.add_argument(
        "-r",
        "--recurse",
        action="store_true",
        dest="recurse",
        default=None,
        help="Recurse down through directories on the command line.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        dest="verbose",
        default=None,
        help="Display more output. -v (default) and -vv " "(noisy)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_const",
        dest="verbose",
        const=-1,
        default=None,
        help="Display little to no output",
    )
    parser.add_argument(
        "-c",
        "--comics",
        action="store_true",
        dest="comics",
        default=None,
        help="Also optimize comic book archives (cbz & cbr)",
    )
    parser.add_argument(
        "-f",
        "--formats",
        type=csv_set,
        action="store",
        dest="formats",
        default=None,
        help="Only optimize images of the specified "
        f"'{FORMAT_DELIMETER}' delimited formats from:"
        f" {all_formats}",
    )
    parser.add_argument(
        "-p",
        "--convert_to_png",
        action="store_const",
        dest="to_png_formats",
        const=PNG_CONVERTABLE_FORMATS,
        default=PNG_FORMATS,
        help=f"Convert {png_lossless_formats} formats to PNG when optimizing.",
    )
    parser.add_argument(
        "-w",
        "--convert_to_webp",
        action="store_const",
        dest="to_webp_formats",
        const=WEBP_CONVERTABLE_FORMATS,
        default=WEBP_FORMATS,
        help=f"Convert {webp_lossless_formats} to Lossless WebP when optimizing.",
    )
    parser.add_argument(
        "-g",
        "--convert_animated_formats",
        action="store_const",
        dest="to_animated_webp_formats",
        const=WEBP_ANIMATED_CONVERTABLE_FORMATS,
        default=None,
        help="Convert animated gifs to animated WebP.",
    )
    parser.add_argument(
        "-S",
        "--no-follow-symlinks",
        action="store_false",
        dest="follow_symlinks",
        default=None,
        help="do not follow symlinks for files and directories",
    )
    parser.add_argument(
        "-b",
        "--bigger",
        action="store_true",
        dest="bigger",
        default=None,
        help="Save optimized files that are larger than " "the originals",
    )
    parser.add_argument(
        "-I",
        "--no_timestamp",
        action="store_false",
        dest="record_timestamp",
        default=None,
        help="Do not record the optimization time in a timestamp file.",
    )
    parser.add_argument(
        "-D",
        "--optimize_after",
        action="store",
        dest="optimize_after",
        default=None,
        type=Timestamp.parse_date_string,
        help="only optimize files after the specified "
        "timestamp. Supersedes .picopt_timestamp file.",
    )
    parser.add_argument(
        "-N",
        "--noop",
        action="store_true",
        dest="test",
        default=None,
        help="Do not replace files with optimized versions",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        dest="list_only",
        default=None,
        help="Only list files that would be optimized",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=VERSION,
        help="Display the version number",
    )
    parser.add_argument(
        "-M",
        "--destroy_metadata",
        action="store_true",
        dest="destroy_metadata",
        default=None,
        help="*Destroy* metadata like EXIF and JFIF",
    )
    parser.add_argument(
        "paths",
        metavar="path",
        type=str,
        nargs="+",
        default=None,
        help="File or directory paths to optimize",
    )
    parser.add_argument(  # TODO remove and use os.cpu
        "-j",
        "--jobs",
        type=int,
        action="store",
        dest="jobs",
        default=None,
        help="Number of parallel jobs to run simultaneously.",
    )
    parser.add_argument(
        "-C",
        "--config",
        type=str,
        action="store",
        default=None,
        help="Path to a config file",
    )

    return parser.parse_args(args[1:])


def run(args: Tuple[str, ...]) -> bool:
    """Process command line arguments and walk inputs."""
    arguments = get_arguments(args)
    arguments_dict = {}
    for key, val in vars(arguments).items():
        if val is not None:
            arguments_dict[key] = val
    if arguments.config is not None:
        rc_path: Optional[Path] = Path(arguments.config)
    else:
        rc_path = None
    arg_namespace = Namespace(**arguments_dict)
    settings = Settings(arg_namespace, rc_path, check_programs=True)
    wob = walk.Walk()
    return wob.run(settings)


def main() -> None:
    """CLI entry point."""
    import sys

    res = run(tuple(sys.argv))
    if not res:
        sys.exit(1)


if __name__ == "__main__":
    main()
