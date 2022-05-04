"""Confuse config for picopt."""
import pathlib
import stat
import time
import typing

from argparse import Namespace
from copy import deepcopy

from confuse import Configuration
from confuse.templates import (
    AttrDict,
    Choice,
    Integer,
    MappingTemplate,
    Optional,
    Path,
    Sequence,
)
from dateutil.parser import parse
from termcolor import cprint

from picopt import PROGRAM_NAME
from picopt.handlers.gif import AnimatedGif, Gif
from picopt.handlers.handler import Format, Handler
from picopt.handlers.image import (
    BPM_FORMAT_OBJ,
    CONVERTABLE_FORMAT_OBJS,
    CONVERTABLE_FORMATS,
    PPM_FORMAT_OBJ,
    TIFF_ANIMATED_FORMAT_OBJ,
    TIFF_FORMAT,
    TIFF_FORMAT_OBJ,
)
from picopt.handlers.jpeg import Jpeg
from picopt.handlers.png import Png
from picopt.handlers.webp import Gif2WebP, WebPLossless, WebPLossy
from picopt.handlers.webp_animated import WebPAnimated
from picopt.handlers.zip import CBZ, EPub, Zip


_PNG_CONVERTABLE_FORMAT_OBJS = CONVERTABLE_FORMAT_OBJS | frozenset(
    [Gif.OUTPUT_FORMAT_OBJ]
)
_WEBP_CONVERTABLE_FORMAT_OBJS = _PNG_CONVERTABLE_FORMAT_OBJS | frozenset(
    [Png.OUTPUT_FORMAT_OBJ]
)
PNG_CONVERTABLE_FORMATS = frozenset(
    [format.format for format in _PNG_CONVERTABLE_FORMAT_OBJS]
)
WEBP_CONVERTABLE_FORMATS = frozenset(
    [format.format for format in _WEBP_CONVERTABLE_FORMAT_OBJS]
)
CONVERT_TO_FORMATS = frozenset(
    (
        Png.OUTPUT_FORMAT,
        WebPLossless.OUTPUT_FORMAT,
        Zip.OUTPUT_FORMAT,
        CBZ.OUTPUT_FORMAT,
    )
)
CONTAINER_CONVERTABLE_FORMATS = frozenset((Zip.INPUT_FORMAT_RAR, CBZ.INPUT_FORMAT_RAR))
DEFAULT_HANDLERS = (Gif, AnimatedGif, Jpeg, Png, WebPLossy, WebPLossless)
HANDLERS = frozenset([*DEFAULT_HANDLERS, Gif2WebP, WebPAnimated, Zip, CBZ, EPub])
ALL_FORMATS: frozenset[str] = (
    frozenset([cls.OUTPUT_FORMAT for cls in HANDLERS])
    | CONVERTABLE_FORMATS
    | frozenset([TIFF_FORMAT])
    | CONTAINER_CONVERTABLE_FORMATS
)
TEMPLATE = MappingTemplate(
    {
        "picopt": MappingTemplate(
            {
                "after": Optional(float),
                "bigger": bool,
                "convert_to": Optional(Sequence(Choice(CONVERT_TO_FORMATS))),
                "keep_metadata": bool,
                "formats": Sequence(Choice(ALL_FORMATS)),
                "ignore": Sequence(str),
                "jobs": Integer(),
                "list_only": bool,
                "paths": Sequence(Path()),
                "recurse": bool,
                "symlinks": bool,
                "test": bool,
                "timestamps": bool,
                "verbose": Integer(),
                "_available_programs": set,
                "_extra_formats": Optional(Sequence(Choice(ALL_FORMATS))),
                "_format_handlers": dict,
            }
        )
    }
)
TIMESTAMPS_CONFIG_KEYS = set(
    (
        "bigger",
        "convert_to",
        "formats",
        "ignore",
        "keep_metadata",
        "recurse",
        "symlinks",
    )
)
# Handlers for formats are listed in priority order
_FORMAT_HANDLERS = {
    PPM_FORMAT_OBJ: {"convert": (WebPLossless, Png)},
    BPM_FORMAT_OBJ: {"convert": (WebPLossless, Png)},
    Gif.OUTPUT_FORMAT_OBJ: {"convert": (Gif2WebP, Png), "native": (Gif,)},
    AnimatedGif.OUTPUT_FORMAT_OBJ: {"convert": (Gif2WebP,), "native": (AnimatedGif,)},
    Jpeg.OUTPUT_FORMAT_OBJ: {"native": (Jpeg,)},
    Png.OUTPUT_FORMAT_OBJ: {"convert": (WebPLossless,), "native": (Png,)},
    WebPLossy.OUTPUT_FORMAT_OBJ: {"native": (WebPLossy,)},
    WebPLossless.OUTPUT_FORMAT_OBJ: {"native": (WebPLossless,)},
    WebPAnimated.OUTPUT_FORMAT_OBJ: {"native": (WebPAnimated,)},
    Zip.OUTPUT_FORMAT_OBJ: {"native": (Zip,)},
    CBZ.OUTPUT_FORMAT_OBJ: {"native": (CBZ,)},
    Zip.INPUT_FORMAT_OBJ_RAR: {"convert": (Zip,)},
    CBZ.INPUT_FORMAT_OBJ_RAR: {"convert": (CBZ,)},
    EPub.OUTPUT_FORMAT_OBJ: {"native": (EPub,)},
    TIFF_FORMAT_OBJ: {"convert": (WebPLossless, Png)},
    TIFF_ANIMATED_FORMAT_OBJ: {"convert": (WebPAnimated,)},
}
MODE_EXECUTABLE = stat.S_IXUSR ^ stat.S_IXGRP ^ stat.S_IXOTH


def _is_external_program_executable(
    program: str, bin_path: typing.Optional[str], verbose: int
) -> bool:
    """Test to see if the external programs can be run."""
    try:
        if not bin_path:
            raise ValueError()
        path = pathlib.Path(bin_path)
        mode = path.stat().st_mode
        result = bool(mode & MODE_EXECUTABLE)
    except Exception:
        if bin_path and verbose:
            cprint(
                f"WARNING: Could not find executable program for {program}", "yelllow"
            )
        result = False

    return result


def _get_available_programs(config: Configuration) -> set:
    """Run the external program tester on the required binaries."""
    verbose = config["picopt"]["verbose"].get(int)
    if not isinstance(verbose, int):
        raise ValueError(f"wrong type for convert_to: {type(verbose)} {verbose}")
    programs = set()
    for handler in HANDLERS:
        for program, bin_path in handler.PROGRAMS.items():
            if (
                program == Handler.INTERNAL
                or program.startswith("pil2")
                or _is_external_program_executable(program, bin_path, verbose)
            ):
                programs.add(program)
    if not programs:
        raise ValueError("No optimizers are available or all optimizers are disabled")
    return programs


def _config_list_to_set(config, key) -> set[str]:
    val_list = config["picopt"][key].get(list)
    if not isinstance(val_list, (tuple, list, set)):
        raise ValueError(f"wrong type for convert_to: {type(val_list)} {val_list}")
    return set(val_list)


def _update_formats(config: Configuration) -> dict:
    formats = _config_list_to_set(config, "formats")
    if "_extra_formats" in config["picopt"]:
        formats |= _config_list_to_set(config, "_extra_formats")

    convert_to = _config_list_to_set(config, "convert_to")
    convert_handlers: dict[typing.Type[Handler], set[Format]] = {}
    if Png.OUTPUT_FORMAT in convert_to:
        formats |= PNG_CONVERTABLE_FORMATS
        format_objs = deepcopy(_PNG_CONVERTABLE_FORMAT_OBJS)
        if TIFF_FORMAT in formats:
            format_objs.add(TIFF_FORMAT_OBJ)
        convert_handlers[Png] = format_objs
    if WebPLossless.OUTPUT_FORMAT in convert_to:
        formats |= WEBP_CONVERTABLE_FORMATS
        format_objs = deepcopy(_WEBP_CONVERTABLE_FORMAT_OBJS)
        if TIFF_FORMAT in formats:
            format_objs.add(TIFF_FORMAT_OBJ)
        convert_handlers[WebPLossless] = format_objs

        convert_handlers[Gif2WebP] = set(
            [Gif.OUTPUT_FORMAT_OBJ, AnimatedGif.OUTPUT_FORMAT_OBJ]
        )
        if TIFF_FORMAT in formats:
            convert_handlers[WebPAnimated] = set([TIFF_ANIMATED_FORMAT_OBJ])
    if Zip.OUTPUT_FORMAT in convert_to:
        formats |= set([Zip.INPUT_FORMAT_RAR])
        convert_handlers[Zip] = set([Zip.INPUT_FORMAT_OBJ_RAR])
    if CBZ.OUTPUT_FORMAT in convert_to:
        formats |= set([CBZ.INPUT_FORMAT_RAR])
        convert_handlers[CBZ] = set([CBZ.INPUT_FORMAT_OBJ_RAR])

    config["picopt"]["formats"].set(sorted(formats))

    return convert_handlers


def _create_format_handler_map(config: Configuration, convert_handlers: dict) -> None:
    """Create a format to handler map from config."""
    available_programs = _get_available_programs(config)
    format_handlers = {}
    formats = config["picopt"]["formats"].get(list)
    if not isinstance(formats, list):
        raise ValueError(f"wrong type for formats: {type(formats)}{formats}")
    formats = set(formats)

    for format, possible_handler_classes_group in _FORMAT_HANDLERS.items():
        if format.format not in formats:
            continue
        for (
            handler_type,
            possible_handler_classes,
        ) in possible_handler_classes_group.items():
            for handler_class in possible_handler_classes:
                available = handler_class.is_handler_available(
                    convert_handlers, available_programs, format
                )
                if available:
                    if format not in format_handlers:
                        format_handlers[format] = {}
                    format_handlers[format][handler_type] = handler_class
                    break
    config["picopt"]["_format_handlers"].set(format_handlers)
    config["picopt"]["_available_programs"].set(available_programs)


def _set_after(config) -> None:
    after = config["picopt"]["after"].get()
    if after is None:
        return

    try:
        timestamp = float(after)
    except ValueError:
        after_dt = parse(after)
        timestamp = time.mktime(after_dt.timetuple())

    config["picopt"]["after"].set(timestamp)


def _set_ignore(config) -> None:
    """Remove duplicates from the ignore list."""
    ignore_list: list[str] = config["picopt"]["ignore"].get(list)
    config["picopt"]["ignore"].set(tuple(sorted(set(ignore_list))))


def _set_timestamps(config) -> None:
    """Set the timestamps attribute."""
    timestamps = (
        config["picopt"]["timestamps"].get(bool)
        and not config["picopt"]["test"].get(bool)
        and not config["picopt"]["list_only"].get(bool)
    )
    config["picopt"]["timestamps"].set(timestamps)


def get_config(
    args: typing.Optional[Namespace] = None, modname=PROGRAM_NAME
) -> AttrDict:
    """Get the config dict, layering env and args over defaults."""
    config = Configuration(PROGRAM_NAME, modname=modname, read=False)
    try:
        config.read()
    except Exception as exc:
        cprint(f"WARNING: {exc}")
    if args and args.picopt and args.picopt.config:
        config.set_file(args.picopt.config)
    config.set_env()
    if args:
        config.set_args(args)
    _set_after(config)
    convert_handlers = _update_formats(config)
    _create_format_handler_map(config, convert_handlers)
    _set_ignore(config)
    _set_timestamps(config)
    ad = config.get(TEMPLATE)
    if not isinstance(ad, AttrDict):
        raise ValueError()
    return ad.picopt
