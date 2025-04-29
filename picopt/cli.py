"""Run pictures through image specific external optimizers."""

import sys
from argparse import Action, ArgumentParser, Namespace, RawDescriptionHelpFormatter
from importlib.metadata import PackageNotFoundError, version

from confuse.exceptions import ConfigError
from termcolor import colored, cprint

from picopt import PROGRAM_NAME
from picopt.config import get_config
from picopt.config.consts import (
    ALL_FORMAT_STRS,
    ARCHIVE_CONVERT_FROM_FORMAT_STRS,
    CB_CONVERT_FROM_FORMAT_STRS,
    DEFAULT_HANDLERS,
    LOSSLESS_IMAGE_CONVERT_TO_FORMAT_STRS,
)
from picopt.exceptions import PicoptError
from picopt.handlers.container.archive.zip import Cbz, Zip
from picopt.walk.walk import Walk

_DEFAULT_FORMAT_STRS = frozenset(
    [handler_cls.OUTPUT_FORMAT_STR for handler_cls in DEFAULT_HANDLERS]
)
_LIST_DELIMETER = ","
try:
    VERSION = version(PROGRAM_NAME)
except PackageNotFoundError:
    VERSION = "test"


class SplitArgsAction(Action):
    """Convert csv string from argparse to a list."""

    def __call__(self, _parser, namespace, values, _option_string=None):
        """Split values string into list."""
        if isinstance(values, str):
            values = tuple(sorted(values.strip().split(_LIST_DELIMETER)))
        setattr(namespace, self.dest, values)


def _comma_join(
    formats: frozenset[str] | tuple[str, ...],
    *,
    space=True,
    final_and=False,
) -> str:
    """Sort and join a sequence into a human readable string."""
    formats = tuple(sorted(formats))
    if len(formats) == 2:  # noqa: PLR2004
        return " or ".join(formats)
    if final_and:
        final = formats[-1]
        formats = formats[:-1]
    else:
        final = ""
    delimiter = ","
    if space:
        delimiter += " "
    result = delimiter.join(formats)
    if final:
        result += f"{delimiter} and {final}"
    return result


COLOR_KEY = (
    ("skipped", "dark_grey", []),
    ("skipped by timestamp", "light_green", ["dark", "bold"]),
    ("copied archive contents unchanged", "green", []),
    ("optimized bigger than original", "light_blue", ["bold"]),
    ("noop on dry run", "dark_grey", ["bold"]),
    ("optimized in same format", "white", []),
    ("converted to another format", "light_cyan", []),
    ("packed into archive", "light_grey", []),
    ("consumed timestamp from archive", "magenta", []),
    ("WARNING", "light_yellow", []),
    ("ERROR", "light_red", []),
)


def get_dot_color_key():
    """Create dot color key."""
    epilogue = "Progress dot colors:\n"
    for text, color, attrs in COLOR_KEY:
        epilogue += "\t" + colored(text, color, attrs=attrs) + "\n"
    return epilogue


def get_arguments(params: tuple[str, ...] | None = None) -> Namespace:
    """Parse the command line."""
    description = "Losslessly optimizes and optionally converts images."
    epilog = get_dot_color_key()
    parser = ArgumentParser(
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
        f"comma delimited formats from: {_comma_join(ALL_FORMAT_STRS)}. "
        f"Defaults to {_comma_join(_DEFAULT_FORMAT_STRS, space=False)}",
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
        help="A list of formats to convert to. "
        "By default formats are not converted to other formats. "
        f"Lossless images may convert to {_comma_join(LOSSLESS_IMAGE_CONVERT_TO_FORMAT_STRS)}.\n"
        f"{_comma_join(ARCHIVE_CONVERT_FROM_FORMAT_STRS, final_and=True)} archives "
        f"may convert to {Zip.OUTPUT_FORMAT_STR}.\n"
        f"{_comma_join(CB_CONVERT_FROM_FORMAT_STRS, final_and=True)} may convert to {Cbz.OUTPUT_FORMAT_STR}.",
    )
    parser.add_argument(
        "-n",
        "--near-lossless",
        action="store_true",
        dest="near_lossless",
        help="Precompress lossless WebP images with near lossless pixel adjustments. Provides more compression for little to no visual quality loss especially for discrete tone images like drawings.",
    )
    parser.add_argument(
        "--png-max",
        action="store_true",
        dest="png_max",
        help="Overzealously optimize pngs with -O5 and Zopfli.",
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
        help="Comma delimited list of case sensitive patterns to ignore. Use '*' as a wildcard.",
    )
    parser.add_argument(
        "-I",
        "--no-ignore-dotfiles",
        dest="ignore_dotfiles",
        default=True,
        action="store_false",
        help="Do not ignore dotfiles. By default they are ignored.",
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
        "-d",
        "--dry_run",
        action="store_true",
        dest="dry_run",
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
        "--strip-metadata",
        action="store_false",
        dest="keep_metadata",
        help="Strip metadata like EXIF, XMP and ICC Profiles",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        action="store",
        dest="jobs",
        help="Number of parallel jobs to run simultaneously. Defaults "
        "to number of available cores.",
    )
    parser.add_argument(
        "-C",
        "--config",
        type=str,
        action="store",
        help="Path to a config file",
    )
    parser.add_argument(
        "-p",
        "--preserve",
        action="store_true",
        help="Preserve file attributes (uid, gid, mode, mtime) after optimization.",
    )
    parser.add_argument(
        "-D",
        "--disable-programs",
        action=SplitArgsAction,
        help="Disable a comma delineated list of external programs from optimizing files.",
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

    # increment verbose
    if pns.verbose is not None and pns.verbose > 0:
        pns.verbose += 1

    return Namespace(picopt=pns)


def main(args: tuple[str, ...] | None = None):
    """Process command line arguments and walk inputs."""
    try:
        arguments = get_arguments(args)

        config = get_config(arguments)
        walker = Walk(config)
        walker.walk()
    except ConfigError as err:
        cprint(f"ERROR: {err}", "red")
        sys.exit(78)
    except PicoptError as err:
        cprint(f"ERROR: {err}", "red")
        sys.exit(1)
    except Exception as exc:
        cprint(f"ERROR: {exc}", "red")
        import traceback

        traceback.print_exception(exc)
        sys.exit(1)
