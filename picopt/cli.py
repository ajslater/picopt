"""Run pictures through image specific external optimizers."""

from __future__ import annotations

import sys
import traceback
from argparse import Action, ArgumentParser, Namespace, RawDescriptionHelpFormatter
from functools import cache
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any

from confuse.exceptions import ConfigError
from termcolor import colored
from typing_extensions import override

from picopt import PROGRAM_NAME
from picopt import plugins as registry
from picopt.config import PicoptConfig
from picopt.doctor import PicoptDoctor
from picopt.exceptions import PicoptError
from picopt.printer import Printer
from picopt.walk.walk import Walk

if TYPE_CHECKING:
    from collections.abc import Sequence

_LIST_DELIMITER = ","


@cache
def _get_version() -> str:
    try:
        return version(PROGRAM_NAME)
    except PackageNotFoundError:
        return "test"


def _default_format_strs() -> tuple[str, ...]:
    """Format strings of every default-enabled plugin's handlers."""
    out: set[str] = set()
    for plugin in registry.iter_plugins():
        if not plugin.default_enabled:
            continue
        for handler_cls in plugin.handlers:
            out.add(handler_cls.OUTPUT_FORMAT_STR)
    return tuple(sorted(out))


def _archive_convert_from_format_strs() -> tuple[str, ...]:
    """Format strings the registry knows how to convert *from* into Zip/Cbz."""
    out: set[str] = set()
    routes = registry.routes_by_format()
    for file_format, (_native, convert_chain) in routes.items():
        if not file_format.archive:
            continue
        for handler_cls in convert_chain:
            if handler_cls.OUTPUT_FORMAT_STR in {"ZIP", "CBZ"}:
                out.add(file_format.format_str)
                break
    return tuple(sorted(out))


def _lossless_image_convert_to_format_strs() -> tuple[str, ...]:
    """Convert-to targets that are lossless image formats."""
    out: set[str] = set()
    for plugin in registry.iter_plugins():
        for handler_cls in plugin.convert_targets:
            if handler_cls.OUTPUT_FILE_FORMAT.archive:
                continue
            if handler_cls.OUTPUT_FILE_FORMAT.lossless:
                out.add(handler_cls.OUTPUT_FORMAT_STR)
    return tuple(sorted(out))


class SplitArgsAction(Action):
    """Convert csv string from argparse to a list."""

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        """Split values string into list."""
        if isinstance(values, str):
            values = tuple(sorted(values.strip().split(_LIST_DELIMITER)))
        setattr(namespace, self.dest, values)


def _comma_join(
    formats: frozenset[str] | tuple[str, ...] | Sequence[str],
    *,
    space: bool = True,
    final_and: bool = False,
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
    delimiter = "," + (" " if space else "")
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


def get_dot_color_key() -> str:
    """Create dot color key."""
    epilogue = "Progress dot colors:\n"
    for text, color, attrs in COLOR_KEY:
        epilogue += "\t" + colored(text, color, attrs=attrs) + "\n"

    epilogue += (
        "\n"
        + colored("doctor mode:", "blue", attrs=["bold"])
        + "\n "
        + colored(PROGRAM_NAME, "light_magenta")
        + " "
        + colored("doctor", "light_green")
        + "\t\tDoctor mode shows available tools.\n"
    )
    return epilogue


def get_arguments(params: tuple[str, ...] | None = None) -> Namespace:
    """Parse the command line."""
    all_format_strs = registry.all_format_strs()
    default_format_strs = _default_format_strs()
    lossless_convert_to = _lossless_image_convert_to_format_strs()
    archive_convert_from = _archive_convert_from_format_strs()

    description = "Losslessly optimizes and optionally converts images."
    epilog = get_dot_color_key()
    parser = ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=RawDescriptionHelpFormatter,
    )
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
        default=1,
        dest="verbose",
        help="Display more output. Can be used multiple times.",
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
        help=(
            f"Only optimize images of the specified comma delimited formats from: "
            f"{_comma_join(all_format_strs)}. "
            f"Defaults to {_comma_join(default_format_strs, space=False)}"
        ),
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
        help=(
            f"A list of formats to convert to. By default formats are not "
            f"converted. Lossless images may convert to "
            f"{_comma_join(lossless_convert_to)}. "
            f"{_comma_join(archive_convert_from, final_and=True)} archives may "
            f"convert to ZIP or CBZ."
        ),
    )
    parser.add_argument(
        "-n",
        "--near-lossless",
        action="store_true",
        dest="near_lossless",
        help="Precompress lossless WebP images with near lossless pixel adjustments.",
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
        "--no-default-ignores",
        dest="ignore_defaults",
        default=True,
        action="store_false",
        help="Do not ignore dotfiles and sparsebundles.",
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
        help="Record the optimization time in a timestamps file.",
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
        "-E",
        "--timestamps-ignore-archive-entry-mtimes",
        dest="timestamps_ignore_archive_entry_mtimes",
        action="store_true",
        default=False,
        help="Use the archive file timestamp instead of archive entry timestamps.",
    )
    parser.add_argument(
        "-A",
        "--after",
        action="store",
        dest="after",
        help="Only optimize files after the specified timestamp.",
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
        help="Number of parallel jobs to run simultaneously.",
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
        help="Disable a comma delineated list of external programs.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        dest="fail_fast",
        help="Stop all optimization on the first error encountered.",
    )
    parser.add_argument(
        "--fail-fast-container",
        action="store_true",
        dest="fail_fast_container",
        help="When an inner repack fails, fail the entire top-level container.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )
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
    return Namespace(picopt=pns)


def main(args: tuple[str, ...] | None = None) -> None:
    """Process command line arguments and walk inputs."""
    # `picopt doctor` is a separate top-level subcommand. It sniffs the cli, if it
    # detects doctor mode it runs a checkup and exits the program.
    # Do this before constructing the main argparser so we don't have to refactor
    # the existing CLI into subparsers.
    PicoptDoctor.parse_cli()

    printer = Printer(2)
    try:
        arguments = get_arguments(args)
        config = PicoptConfig(printer).get_config(arguments)
        walker = Walk(config)
        walker.walk()
    except ConfigError as err:
        printer.error("", err)
        sys.exit(78)
    except PicoptError as err:
        printer.error("", err)
        sys.exit(1)
    except Exception as exc:
        printer.error("", exc)
        traceback.print_exception(exc)
        sys.exit(1)
