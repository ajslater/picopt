#!/usr/bin/env python3
"""Run pictures through image specific external optimizers."""
import argparse

from argparse import Namespace
from pathlib import Path
from typing import Optional
from typing import Set
from typing import Tuple

import pkg_resources

from picopt import PROGRAM_NAME
from picopt import walk
from picopt.formats.all_formats import ALL_FORMATS
from picopt.formats.png import Png
from picopt.formats.programs import PROGRAMS
from picopt.settings import Settings
from picopt.timestamp import Timestamp


FORMAT_DELIMETER = ","
DISTRIBUTION = pkg_resources.get_distribution(PROGRAM_NAME)


def csv_set(csv_str: str) -> Set[str]:
    """Convert csv string from argparse to a list."""
    return set(csv_str.upper().split(FORMAT_DELIMETER))


def get_arguments(args: Tuple[str, ...]) -> Namespace:
    """Parse the command line."""
    usage = "%(prog)s [arguments] [paths]"
    programs_str = ", ".join(
        (prog.__func__.__name__ for prog in PROGRAMS)  # type: ignore
    )
    description = f"Uses {programs_str} if they are on the path."
    parser = argparse.ArgumentParser(usage=usage, description=description)
    all_formats = ", ".join(sorted(ALL_FORMATS))
    lossless_formats = ", ".join(Png.LOSSLESS_FORMATS)
    parser.add_argument(
        "-R",
        "--no_recurse",
        action="store_false",
        dest="recurse",
        default=None,
        help="Do not recurse down through command line paths.",
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
        "-Q",
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
        help="Only optimize images of the specifed"
        f"'{FORMAT_DELIMETER}' delimited formats from:"
        f" {all_formats}",
    )
    parser.add_argument(
        "-Y",
        "--no_convert_type",
        action="store_const",
        dest="to_png_formats",
        const=Png.FORMATS,
        default=None,
        help="Do not convert other lossless formats"
        f"like {lossless_formats} to PNG when "
        f"optimizing. By default, {PROGRAM_NAME}"
        " does convert these formats to PNG",
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
        "timestamp. Supercedes .picopt_timestamp file.",
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
        version=DISTRIBUTION.version,
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
    parser.add_argument(
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
