"""Confuse config for picopt."""
import shutil
import subprocess
import time
from argparse import Namespace
from collections.abc import ItemsView, Iterable
from dataclasses import dataclass, fields
from pathlib import Path
from types import MappingProxyType

from confuse import Configuration, Subview
from confuse.templates import (
    AttrDict,
    Choice,
    Integer,
    MappingTemplate,
    Optional,
    Sequence,
)
from confuse.templates import Path as ConfusePath
from dateutil.parser import parse
from termcolor import cprint

from picopt import PROGRAM_NAME
from picopt.formats import (
    CONVERTIBLE_ANIMATED_FILE_FORMATS,
    CONVERTIBLE_FILE_FORMATS,
    LOSSLESS_FORMAT_STRS,
    MPO_FILE_FORMAT,
    FileFormat,
)
from picopt.handlers.gif import Gif, GifAnimated
from picopt.handlers.handler import Handler
from picopt.handlers.jpeg import Jpeg
from picopt.handlers.png import Png
from picopt.handlers.png_animated import PngAnimated
from picopt.handlers.svg import Svg
from picopt.handlers.webp import WebPLossless
from picopt.handlers.webp_animated import WebPAnimatedLossless
from picopt.handlers.zip import Cbr, Cbz, EPub, Rar, Zip

###########################
# Confuse Config Template #
###########################
_CONVERT_TO_FORMAT_STRS = frozenset(
    {
        cls.OUTPUT_FORMAT_STR
        for cls in (
            Png,
            PngAnimated,
            WebPLossless,
            WebPAnimatedLossless,
            Zip,
            Cbz,
            Jpeg,
        )
    }
)
_CONTAINER_CONVERTIBLE_FORMAT_STRS = frozenset(
    {cls.INPUT_FORMAT_STR for cls in (Rar, Cbr)}
)

DEFAULT_HANDLERS = frozenset(
    {Gif, GifAnimated, Jpeg, Png, WebPLossless, WebPAnimatedLossless}
)
_ALL_HANDLERS = frozenset(
    DEFAULT_HANDLERS
    | frozenset(
        {
            Zip,
            Rar,
            Svg,
            Cbz,
            Cbr,
            EPub,
        }
    )
)
ALL_FORMAT_STRS: frozenset[str] = (
    frozenset([cls.OUTPUT_FORMAT_STR for cls in _ALL_HANDLERS])
    | LOSSLESS_FORMAT_STRS
    | _CONTAINER_CONVERTIBLE_FORMAT_STRS
    | {MPO_FILE_FORMAT.format_str}
)
TEMPLATE = MappingTemplate(
    {
        PROGRAM_NAME: MappingTemplate(
            {
                "after": Optional(float),
                "bigger": bool,
                "convert_to": Optional(Sequence(Choice(_CONVERT_TO_FORMAT_STRS))),
                "extra_formats": Optional(Sequence(Choice(ALL_FORMAT_STRS))),
                "formats": Sequence(Choice(ALL_FORMAT_STRS)),
                "ignore": Sequence(str),
                "jobs": Integer(),
                "keep_metadata": bool,
                "list_only": bool,
                "near_lossless": bool,
                "paths": Sequence(ConfusePath()),
                "preserve": bool,
                "recurse": bool,
                "symlinks": bool,
                "test": bool,
                "timestamps": bool,
                "timestamps_check_config": bool,
                "verbose": Integer(),
                "computed": Optional(
                    MappingTemplate(
                        {
                            "native_handlers": dict,
                            "convert_handlers": dict,
                            "handler_stages": dict,
                        }
                    )
                ),
            }
        )
    }
)
TIMESTAMPS_CONFIG_KEYS = {
    "bigger",
    "convert_to",
    "formats",
    "ignore",
    "keep_metadata",
    "near_lossless",
    "recurse",
    "symlinks",
}


########################
# File Format Handlers #
########################
@dataclass
class FileFormatHandlers:
    """FileFormat handlers for a File FileFormat."""

    convert: tuple[type[Handler], ...] = ()
    native: tuple[type[Handler], ...] = ()

    def items(self) -> ItemsView[str, tuple[type[Handler], ...]]:
        """Return both fields."""
        return {
            field.name: tuple(getattr(self, field.name)) for field in fields(self)
        }.items()


# Handlers for formats are listed in priority order
_LOSSLESS_CONVERTIBLE_FORMAT_HANDLERS = MappingProxyType(
    {
        ffmt: FileFormatHandlers(convert=(WebPLossless, Png))
        for ffmt in CONVERTIBLE_FILE_FORMATS
    }
)
_LOSSLESS_CONVERTIBLE_ANIMATED_FORMAT_HANDLERS = MappingProxyType(
    {
        ffmt: FileFormatHandlers(convert=(WebPAnimatedLossless, PngAnimated))
        for ffmt in CONVERTIBLE_ANIMATED_FILE_FORMATS
    }
)
_FORMAT_HANDLERS = MappingProxyType(
    {
        **_LOSSLESS_CONVERTIBLE_FORMAT_HANDLERS,
        **_LOSSLESS_CONVERTIBLE_ANIMATED_FORMAT_HANDLERS,
        Gif.OUTPUT_FILE_FORMAT: FileFormatHandlers(
            convert=(WebPLossless, Png),
            native=(Gif,),
        ),
        GifAnimated.OUTPUT_FILE_FORMAT: FileFormatHandlers(
            convert=(WebPAnimatedLossless, PngAnimated),
            native=(GifAnimated,),
        ),
        MPO_FILE_FORMAT: FileFormatHandlers(convert=(Jpeg,)),
        Jpeg.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(Jpeg,)),
        Png.OUTPUT_FILE_FORMAT: FileFormatHandlers(
            convert=(WebPLossless,), native=(Png,)
        ),
        PngAnimated.OUTPUT_FILE_FORMAT: FileFormatHandlers(
            convert=(WebPAnimatedLossless,), native=(PngAnimated,)
        ),
        WebPLossless.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(WebPLossless,)),
        WebPAnimatedLossless.OUTPUT_FILE_FORMAT: FileFormatHandlers(
            native=(WebPAnimatedLossless,)
        ),
        Svg.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(Svg,)),
        Zip.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(Zip,)),
        Cbz.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(Cbz,)),
        Rar.INPUT_FILE_FORMAT: FileFormatHandlers(convert=(Rar,)),
        Cbr.INPUT_FILE_FORMAT: FileFormatHandlers(convert=(Cbr,)),
        EPub.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(EPub,)),
    }
)


def _print_formats_config(handled_format_strs, convert_format_strs) -> None:
    """Print verbose init messages."""
    handled_format_list = ", ".join(sorted(handled_format_strs))
    cprint(f"Optimizing formats: {handled_format_list}")
    for convert_to_format_str, format_strs in convert_format_strs.items():
        convert_from_list = sorted(format_strs)
        if not convert_from_list:
            return
        convert_from = ", ".join(convert_from_list)
        cprint(f"Converting {convert_from} to {convert_to_format_str}", "cyan")


def _config_formats_list_to_set(config: Subview, key: str) -> frozenset[str]:
    val_list: Iterable = config[key].get(list) if key in config else []  # type: ignore
    val_set = set()
    for val in val_list:
        val_set.add(val.upper())
    return frozenset(val_set)


def _set_all_format_strs(config: Subview) -> frozenset[str]:
    all_format_strs = _config_formats_list_to_set(config, "formats")
    extra_format_strs = _config_formats_list_to_set(config, "extra_formats")

    all_format_strs |= extra_format_strs

    config["formats"] = tuple(sorted(all_format_strs))

    return frozenset(all_format_strs)


def _get_handler_stages(
    handler_class: type[Handler],
) -> dict[str, tuple[str, ...]]:
    """Get the program stages for each handler."""
    stages = {}
    for program_priority_list in handler_class.PROGRAMS:
        for program in program_priority_list:
            if program.startswith(("pil2", Handler.INTERNAL)):
                exec_args = None
            elif program.startswith("npx_"):
                bin_path = shutil.which("npx")
                if not bin_path:
                    continue
                exec_args = (bin_path, "--no", *program.split("_")[1:])
                # XXX sucks but easiest way to determine if an npx prog exists is
                # running it.
                try:
                    subprocess.run(
                        exec_args,  # noqa S603
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except (subprocess.CalledProcessError, FileNotFoundError, OSError):
                    continue
            else:
                bin_path = shutil.which(program)
                if not bin_path:
                    continue
                exec_args = (bin_path,)
            stages[program] = exec_args
            break
    return stages


def _set_format_handler_map(
    config: Subview,
) -> None:
    """Create a format to handler map from config."""
    all_format_strs = _set_all_format_strs(config)
    convert_to = _config_formats_list_to_set(config, "convert_to")

    native_handlers: dict[FileFormat, type[Handler]] = {}
    convert_handlers: dict[FileFormat, type[Handler]] = {}
    handler_stages: dict[type[Handler], dict[str, tuple[str, ...]]] = {}

    handled_format_strs = set()
    convert_format_strs = {}

    for file_format, possible_file_handlers in _FORMAT_HANDLERS.items():
        if file_format.format_str not in all_format_strs:
            continue
        for (
            handler_type,
            possible_handler_classes,
        ) in sorted(possible_file_handlers.items()):
            for handler_class in possible_handler_classes:
                if (
                    handler_type == "convert"
                    and handler_class.OUTPUT_FILE_FORMAT.format_str not in convert_to
                ):
                    continue

                # Get handler stages by class with caching
                if handler_class not in handler_stages:
                    handler_stages[handler_class] = _get_handler_stages(handler_class)
                stages = handler_stages.get(handler_class)
                if not stages:
                    continue

                if handler_type == "convert":
                    if handler_class.OUTPUT_FORMAT_STR not in convert_format_strs:
                        convert_format_strs[handler_class.OUTPUT_FORMAT_STR] = set()
                    convert_format_strs[handler_class.OUTPUT_FORMAT_STR].add(
                        file_format.format_str
                    )
                    convert_handlers[file_format] = handler_class
                else:
                    native_handlers[file_format] = handler_class

                handled_format_strs.add(file_format.format_str)
                break

    convert_handlers = native_handlers | convert_handlers

    config["computed"]["native_handlers"].set(native_handlers)
    config["computed"]["convert_handlers"].set(convert_handlers)
    config["computed"]["handler_stages"].set(handler_stages)
    _print_formats_config(handled_format_strs, convert_format_strs)


#########################
# Other Computed Config #
#########################
def _set_after(config: Subview) -> None:
    after = config["after"].get()
    if after is None:
        return

    try:
        timestamp = float(after)  # type: ignore
    except ValueError:
        after_dt = parse(after)  # type: ignore
        timestamp = time.mktime(after_dt.timetuple())

    config["after"].set(timestamp)
    if timestamp is not None:
        after = time.ctime(timestamp)
        cprint(f"Optimizing after {after}")


def _set_ignore(config: Subview) -> None:
    """Remove duplicates from the ignore list."""
    ignore: Iterable = config["ignore"].get(list)  # type: ignore
    ignore = tuple(sorted(ignore))
    config["ignore"].set(ignore)
    if ignore:
        verbose: int = config["verbose"].get(int)  # type: ignore
        if verbose > 1:
            ignore_list = ",".join(ignore)
            cprint(f"Ignoring: {ignore_list}", "cyan")


def _set_timestamps(config: Subview) -> None:
    """Set the timestamps attribute."""
    timestamps = (
        config["timestamps"].get(bool)
        and not config["test"].get(bool)
        and not config["list_only"].get(bool)
    )
    config["timestamps"].set(timestamps)
    verbose: int = config["verbose"].get(int)  # type: ignore
    if verbose > 1:
        if timestamps:
            roots = set()
            paths: Iterable = config["paths"].get(list)  # type: ignore
            for path_str in paths:
                path = Path(path_str)
                if path.is_dir():
                    roots.add(str(path))
                else:
                    roots.add(str(path.parent))
            roots_str = ", ".join(sorted(roots))
            ts_str = f"Setting a timestamp file at the top of each directory tree: {roots_str}"
        else:
            ts_str = "Not setting timestamps."
        cprint(ts_str, "cyan")


def get_config(args: Namespace | None = None, modname=PROGRAM_NAME) -> AttrDict:
    """Get the config dict, layering env and args over defaults."""
    config = Configuration(PROGRAM_NAME, modname=modname, read=False)
    config.read()
    if args and args.picopt and args.picopt.config:
        config.set_file(args.picopt.config)
    config.set_env()
    if args:
        config.set_args(args)
    config_program = config[PROGRAM_NAME]
    _set_format_handler_map(config_program)
    _set_after(config_program)
    _set_ignore(config_program)
    _set_timestamps(config_program)
    ad = config.get(TEMPLATE)
    if not isinstance(ad, AttrDict):
        msg = "Not a valid config"
        raise TypeError(msg)
    return ad.picopt
