"""Run pictures through image specific external optimizers."""
import argparse
import sys
from argparse import Action, Namespace, RawDescriptionHelpFormatter
from importlib.metadata import PackageNotFoundError, version
from typing import Optional

from termcolor import colored, cprint

from picopt import PROGRAM_NAME, walk
from picopt.config import ALL_FORMAT_STRS, DEFAULT_HANDLERS, get_config
from picopt.handlers.png import Png
from picopt.handlers.webp import WebP
from picopt.handlers.zip import CBR, Rar

DEFAULT_FORMAT_STRS = frozenset(
    [handler_cls.OUTPUT_FORMAT_STR for handler_cls in DEFAULT_HANDLERS]
)
EXTRA_FORMAT_STRS = ALL_FORMAT_STRS - DEFAULT_FORMAT_STRS
FORMAT_DELIMETER = ","
try:
    VERSION = version(PROGRAM_NAME)
except PackageNotFoundError:
    VERSION = "test"


class SplitArgsAction(Action):
    """Convert csv string from argparse to a list."""

    def __call__(self, _parser, namespace, values, _option_string=None):
        """Split values string into list."""
        if isinstance(values, str):
            values = tuple(sorted(values.strip().split(FORMAT_DELIMETER)))
        setattr(namespace, self.dest, values)


def _comma_join(formats: frozenset[str]) -> str:
    """Sort and join a sequence into a human readable string."""
    return ", ".join(sorted(formats))


def get_arguments(params: Optional[tuple[str, ...]] = None) -> Namespace:
    """Parse the command line."""
    description = "Losslessly optimizes and optionally converts images."
    epilog = (
        "progress colors:",
        colored("skipped", "white", attrs=["dark"]),
        colored("skipped by timestamp", "green"),
        colored("optimization bigger than original", "blue", attrs=["bold"]),
        "optimized",
        colored("converted format", "cyan"),
        colored("warning", "yellow"),
        colored("error", "red"),
    )
    epilog = "\n  ".join(epilog)
    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=RawDescriptionHelpFormatter,
    )
    ###########
    # Options #
    ###########
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
        help="Display more output. Can be used multiple times for "
        "increasingly noisy output.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_const",
        dest="verbose",
        const=0,
        help="Display little to no output",
    )
    parser.add_argument(
        "-f",
        "--formats",
        action=SplitArgsAction,
        dest="formats",
        help="Only optimize images of the specified "
        f"'{FORMAT_DELIMETER}' delimited formats from: {_comma_join(ALL_FORMAT_STRS)}. "
        f"Defaults to {_comma_join(DEFAULT_FORMAT_STRS)}",
    )
    parser.add_argument(
        "-x",
        "--extra-formats",
        action=SplitArgsAction,
        dest="extra_formats",
        help="Append additional formats to the default formats.",
    )
    parser.add_argument(
        "-c",
        "--convert-to",
        action=SplitArgsAction,
        dest="convert_to",
        help="A list of formats to convert to. Lossless images may convert to"
        f" {Png.OUTPUT_FORMAT_STR} or {WebP.OUTPUT_FORMAT_STR}."
        f" {Rar.INPUT_FORMAT_STR} archives"
        f" may convert to {Rar.OUTPUT_FORMAT_STR} or {CBR.OUTPUT_FORMAT_STR}."
        " By default formats are not converted to other formats.",
    )
    parser.add_argument(
        "-S",
        "--no-symlinks",
        action="store_false",
        dest="symlinks",
        help="Do not follow symlinks for files and directories",
    )
    parser.add_argument(
        "-i",
        "--ignore",
        action=SplitArgsAction,
        dest="ignore",
        help="List of globs to ignore.",
    )
    parser.add_argument(
        "-b",
        "--bigger",
        action="store_true",
        dest="bigger",
        help="Save optimized files that are larger than the originals",
    )
    parser.add_argument(
        "-t",
        "--timestamps",
        action="store_true",
        dest="timestamps",
        help="Record the optimization time in a timestamps file. "
        "Do not optimize files that are older than their timestamp record.",
    )
    parser.add_argument(
        "-N",
        "--timestamps-no-check-config",
        dest="timestamps_check_config",
        action="store_false",
        default=True,
        help="Do not compare program config options with loaded timestamps.",
    )
    parser.add_argument(
        "-A",
        "--after",
        action="store",
        dest="after",
        help="Only optimize files after the specified timestamp. "
        "Supersedes recorded timestamp files. Can be an epoch number or "
        "datetime string",
    )
    parser.add_argument(
        "-T",
        "--test",
        action="store_true",
        dest="test",
        help="Report how much would be saved, but do not replace files.",
    )
    parser.add_argument(
        "-L",
        "--list",
        action="store_true",
        dest="list_only",
        help="Only list files that would be optimized",
    )

    parser.add_argument(
        "-M",
        "--destroy-metadata",
        action="store_false",
        dest="keep_metadata",
        help="Destroy metadata like EXIF and ICC Profiles",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        action="store",
        dest="jobs",
        help="Number of parallel jobs to run simultaneously. Defaults "
        "to maximum available.",
    )
    parser.add_argument(
        "-C",
        "--config",
        type=str,
        action="store",
        help="Path to a config file",
    )
    ###########
    # Actions #
    ###########
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    ###########
    # Targets #
    ###########
    parser.add_argument(
        "paths",
        metavar="path",
        type=str,
        nargs="+",
        help="File or directory paths to optimize",
    )

    if params is not None:
        params = params[1:]

    pns = parser.parse_args(params)

    # Move extra_formats to computed namespace
    pns.computed = Namespace(extra_formats=pns.extra_formats)
    delattr(pns, "extra_formats")

    # increment verbose
    if pns.verbose is not None and pns.verbose > 0:
        pns.verbose += 1

    return Namespace(picopt=pns)


def main(args: Optional[tuple[str, ...]] = None) -> bool:
    """Process command line arguments and walk inputs."""
    try:
        arguments = get_arguments(args)

        config = get_config(arguments)
        wob = walk.Walk(config)
        return wob.run()
    except Exception as exc:
        cprint(f"ERROR: {exc}", "red")
        import traceback

        traceback.print_exception(exc)
        sys.exit(1)
