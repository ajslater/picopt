#!/usr/bin/env python3
"""Run pictures through image specific external optimizers."""
import argparse
import sys

from argparse import Action, Namespace
from importlib.metadata import PackageNotFoundError, version
from typing import Set, Tuple

from picopt import PROGRAM_NAME, walk
from picopt.config import (
    ALL_FORMATS,
    DEFAULT_HANDLERS,
    PNG_CONVERTABLE_FORMATS,
    WEBP_CONVERTABLE_FORMATS,
    get_config,
)
from picopt.handlers.image import TIFF_FORMAT
from picopt.handlers.zip import CBZ, EPub, Zip


DEFAULT_FORMATS = set([handler_cls.OUTPUT_FORMAT for handler_cls in DEFAULT_HANDLERS])
FORMAT_DELIMETER = ","
try:
    VERSION = version(PROGRAM_NAME)
except PackageNotFoundError:
    VERSION = "test"


class SplitArgsAction(Action):
    """Convert csv string from argparse to a list."""

    def __call__(self, parser, namespace, values, option_string=None):
        """Split values string into list."""
        if isinstance(values, str):
            values = tuple(sorted(values.split(FORMAT_DELIMETER)))
        super().__call__(parser, namespace, values, option_string)


class StoreConstSubKeyAction(Action):
    """Store const in subkey."""

    def __init__(
        self,
        option_strings,
        dest,
        const=None,
        default=None,
        required=False,
        help=None,
        _metavar=None,
    ):
        """Init."""
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            const=const,
            default=default,
            required=required,
            help=help,
        )

    def __call__(self, _parser, namespace, _values, _option_string=None):
        """Assign const to referenced subkey."""
        key, sub_key = self.dest.split(".")
        if key not in namespace:
            namespace.__dict__[key] = {}
        namespace.__dict__[key][sub_key] = self.const


def _comma_join(formats: Set[str]) -> str:
    """Sort and join a sequence into a human readable string."""
    return ", ".join(sorted(formats))


def get_arguments(args: Tuple[str, ...]) -> Namespace:
    """Parse the command line."""
    usage = "%(prog)s [arguments] [paths]"
    description = "Losslessly optimizes and optionally converts images."
    parser = argparse.ArgumentParser(usage=usage, description=description)
    parser.add_argument(
        "-r",
        "--recurse",
        action="store_true",
        dest="recurse",
        help="Recurse down through directories on the command line.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        dest="verbose",
        help="Display more output. -v (default) and -vv " "(noisy)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_const",
        dest="verbose",
        const=-1,
        help="Display little to no output",
    )
    parser.add_argument(
        "-c",
        "--cbz",
        action="append_const",
        dest="_extra_formats",
        const=CBZ.OUTPUT_FORMAT,
        help="Optimize comic book zip archives. Implies --recursive",
    )
    parser.add_argument(
        "-z",
        "--zipfiles",
        action="append_const",
        dest="_extra_formats",
        const=Zip.OUTPUT_FORMAT,
        help="Optimize images inside of zipfiles. Implies --recursive",
    )
    parser.add_argument(
        "-e",
        "--epub",
        action="append_const",
        dest="_extra_formats",
        const=EPub.OUTPUT_FORMAT,
        help="Optimize images inside of ePubs. Implies --recursive",
    )
    parser.add_argument(
        "-t",
        "--tiff",
        action="append_const",
        dest="_extra_formats",
        const=TIFF_FORMAT,
        help="Convert lossless TIFFs to PNG or WEBP. Requires -p or -w to activate.",
    )
    parser.add_argument(
        "-f",
        "--formats",
        action=SplitArgsAction,
        dest="formats",
        help="Only optimize images of the specified "
        f"'{FORMAT_DELIMETER}' delimited formats from: {_comma_join(ALL_FORMATS)}. "
        f"Defaults to {_comma_join(DEFAULT_FORMATS)}",
    )
    parser.add_argument(
        "-p",
        "--convert_to_png",
        action=StoreConstSubKeyAction,
        dest="convert_to.PNG",
        const=True,
        help=f"Convert {_comma_join(PNG_CONVERTABLE_FORMATS)} formats to "
        "PNG when optimizing.",
    )
    parser.add_argument(
        "-w",
        "--convert_to_webp",
        action=StoreConstSubKeyAction,
        dest="convert_to.WEBP",
        const=True,
        help=f"Convert {_comma_join(WEBP_CONVERTABLE_FORMATS)} to "
        "Lossless WebP when optimizing.",
    )
    parser.add_argument(
        "-i",
        "--convert_to_zip",
        action=StoreConstSubKeyAction,
        dest="convert_to.ZIP",
        const=True,
        help="Convert RAR to Zip when optimizing.",
    )
    parser.add_argument(
        "-d",
        "--convert_to_cbz",
        action=StoreConstSubKeyAction,
        dest="convert_to.CBZ",
        const=True,
        help="Convert CBR to CBZ when optimizing.",
    )
    parser.add_argument(
        "-S",
        "--no-follow-symlinks",
        action="store_false",
        dest="follow_symlinks",
        help="do not follow symlinks for files and directories",
    )
    parser.add_argument(
        "-b",
        "--bigger",
        action="store_true",
        dest="bigger",
        help="Save optimized files that are larger than " "the originals",
    )
    parser.add_argument(
        "-I",
        "--no_timestamp",
        action="store_false",
        dest="record_timestamp",
        help="Do not record the optimization time in a timestamp file.",
    )
    parser.add_argument(
        "-A",
        "--after",
        action="store",
        dest="after",
        help="Only optimize files after the specified "
        "timestamp. Supersedes recorded timestamp files.",
    )
    parser.add_argument(
        "-T",
        "--test",
        action="store_true",
        dest="test",
        help="Report how much would be saved, but do not replace files.",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        dest="list_only",
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
        help="Number of parallel jobs to run simultaneously. Defaults to maximum.",
    )
    parser.add_argument(
        "-C",
        "--config",
        type=str,
        action="store",
        help="Path to a config file",
    )

    return parser.parse_args(args[1:])


def run(args: Tuple[str, ...]) -> bool:
    """Process command line arguments and walk inputs."""
    arguments = get_arguments(args)
    config = get_config(arguments)
    wob = walk.Walk(config)
    return wob.run()


def main() -> None:
    """CLI entry point."""
    res = run(tuple(sys.argv))
    if not res:
        sys.exit(1)


if __name__ == "__main__":
    main()
