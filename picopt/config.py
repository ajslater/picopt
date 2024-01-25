"""Confuse config for picopt."""
import pathlib
import stat
import time
import typing
from argparse import Namespace
from copy import deepcopy
from dataclasses import dataclass, fields
from typing import Any

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
from picopt.handlers.handler import FileFormat, Handler
from picopt.handlers.image import (
    BPM_FILE_FORMAT,
    CONVERTABLE_FILE_FORMATS,
    CONVERTABLE_FORMAT_STRS,
    PNG_ANIMATED_FILE_FORMAT,
    PPM_FILE_FORMAT,
    TIFF_ANIMATED_FILE_FORMAT,
    TIFF_FILE_FORMAT,
    TIFF_FORMAT_STR,
)
from picopt.handlers.jpeg import Jpeg
from picopt.handlers.png import Png
from picopt.handlers.webp import Gif2WebP, WebPLossless
from picopt.handlers.webp_animated import WebPAnimatedLossless
from picopt.handlers.zip import CBR, CBZ, EPub, Rar, Zip

_PNG_CONVERTABLE_FILE_FORMATS = CONVERTABLE_FILE_FORMATS | frozenset(
    [Gif.OUTPUT_FILE_FORMAT]
)
_WEBP_CONVERTABLE_FILE_FORMATS = _PNG_CONVERTABLE_FILE_FORMATS | frozenset(
    [Png.OUTPUT_FILE_FORMAT]
)
PNG_CONVERTABLE_FORMAT_STRS = frozenset(
    [img_format.format_str for img_format in _PNG_CONVERTABLE_FILE_FORMATS]
)
WEBP_CONVERTABLE_FORMAT_STRS = frozenset(
    [img_format.format_str for img_format in _WEBP_CONVERTABLE_FILE_FORMATS]
)
CONVERT_TO_FORMAT_STRS = frozenset(
    (
        Png.OUTPUT_FORMAT_STR,
        WebPLossless.OUTPUT_FORMAT_STR,
        Zip.OUTPUT_FORMAT_STR,
        CBZ.OUTPUT_FORMAT_STR,
    )
)
CONTAINER_CONVERTABLE_FORMAT_STRS = frozenset(
    (Rar.INPUT_FORMAT_STR, CBR.INPUT_FORMAT_STR)
)
DEFAULT_HANDLERS = (Gif, AnimatedGif, Jpeg, Png, WebPLossless)
HANDLERS = frozenset(
    [
        *DEFAULT_HANDLERS,
        Gif2WebP,
        WebPAnimatedLossless,
        Zip,
        Rar,
        CBZ,
        CBR,
        EPub,
    ]
)
ALL_FORMAT_STRS: frozenset[str] = (
    frozenset([cls.OUTPUT_FORMAT_STR for cls in HANDLERS])
    | CONVERTABLE_FORMAT_STRS
    | frozenset([TIFF_FORMAT_STR])
    | CONTAINER_CONVERTABLE_FORMAT_STRS
)
TEMPLATE = MappingTemplate(
    {
        PROGRAM_NAME: MappingTemplate(
            {
                "after": Optional(float),
                "bigger": bool,
                "convert_to": Optional(Sequence(Choice(CONVERT_TO_FORMAT_STRS))),
                "formats": Sequence(Choice(ALL_FORMAT_STRS)),
                "ignore": Sequence(str),
                "jobs": Integer(),
                "keep_metadata": bool,
                "list_only": bool,
                "paths": Sequence(Path()),
                "recurse": bool,
                "symlinks": bool,
                "test": bool,
                "timestamps": bool,
                "timestamps_check_config": bool,
                "verbose": Integer(),
                "computed": Optional(
                    MappingTemplate(
                        {
                            "available_programs": frozenset,
                            "convertable_formats": Optional(
                                MappingTemplate(
                                    {
                                        "webp": Optional(frozenset),
                                        "png": Optional(frozenset),
                                    }
                                )
                            ),
                            "extra_formats": Optional(
                                Sequence(Choice(ALL_FORMAT_STRS))
                            ),
                            "format_handlers": dict,
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
    "recurse",
    "symlinks",
}


@dataclass
class FileFormatHandlers:
    """FileFormat handlers for a File FileFormat."""

    # Pyright can't enforce a list of subclasses
    # https://github.com/microsoft/pyright/issues/130
    # https://peps.python.org/pep-0483/#covariance-and-contravariance
    convert: Any = None
    native: Any = None

    def _field_to_tuple(self, field):
        """Convert a handler to a tuple of handlers."""
        val = getattr(self, field.name)
        if val is None:
            setattr(self, field.name, ())
        elif not isinstance(val, tuple):
            val = (val,)
            setattr(self, field.name, val)

    def __post_init__(self):
        """Convert raw handlers into tuples."""
        for field in fields(self):
            self._field_to_tuple(field)

    def items(self):
        """Return both fields."""
        return {"convert": self.convert, "native": self.native}.items()


# Handlers for formats are listed in priority order
_FORMAT_HANDLERS = {
    PPM_FILE_FORMAT: FileFormatHandlers(convert=(WebPLossless, Png)),
    BPM_FILE_FORMAT: FileFormatHandlers(convert=(WebPLossless, Png)),
    Gif.OUTPUT_FILE_FORMAT: FileFormatHandlers(convert=(Gif2WebP, Png), native=Gif),
    AnimatedGif.OUTPUT_FILE_FORMAT: FileFormatHandlers(
        convert=Gif2WebP, native=AnimatedGif
    ),
    Jpeg.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=Jpeg),
    Png.OUTPUT_FILE_FORMAT: FileFormatHandlers(convert=WebPLossless, native=Png),
    WebPLossless.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=WebPLossless),
    WebPAnimatedLossless.OUTPUT_FILE_FORMAT: FileFormatHandlers(
        native=WebPAnimatedLossless
    ),
    Zip.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=Zip),
    CBZ.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=CBZ),
    Rar.INPUT_FILE_FORMAT: FileFormatHandlers(convert=Rar),
    CBR.INPUT_FILE_FORMAT: FileFormatHandlers(convert=CBR),
    EPub.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=EPub),
    TIFF_FILE_FORMAT: FileFormatHandlers(convert=(WebPLossless, Png)),
    TIFF_ANIMATED_FILE_FORMAT: FileFormatHandlers(convert=WebPAnimatedLossless),
    PNG_ANIMATED_FILE_FORMAT: FileFormatHandlers(convert=WebPAnimatedLossless),
}
MODE_EXECUTABLE = stat.S_IXUSR ^ stat.S_IXGRP ^ stat.S_IXOTH


def _is_external_program_executable(
    program: str, bin_path: typing.Optional[str], verbose: int
) -> bool:
    """Test to see if the external programs can be run."""
    try:
        if not bin_path:
            return False
        path = pathlib.Path(bin_path)
        mode = path.stat().st_mode
        result = bool(mode & MODE_EXECUTABLE)
    except Exception:
        if bin_path and verbose:
            cprint(
                f"WARNING: Could not find executable program for '{program}'", "yellow"
            )
        result = False

    return result


def _get_available_programs(config: Configuration) -> frozenset:
    """Run the external program tester on the required binaries."""
    verbose = config[PROGRAM_NAME]["verbose"].get(int)
    if not isinstance(verbose, int):
        msg = f"wrong type for convert_to: {type(verbose)} {verbose}"
        raise TypeError(msg)
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
        msg = "No optimizers are available or all optimizers are disabled"
        raise ValueError(msg)
    return frozenset(programs)


def _config_formats_list_to_set(config, key, computed=False) -> frozenset[str]:
    source = config[PROGRAM_NAME]
    if computed:
        source = source["computed"]
    val_list = source[key].get()
    val_set = set()
    for val in val_list:
        val_set.add(val.upper())
    return frozenset(val_set)


def _update_formats_png(format_strs, convert_handlers, config):
    """Update formats if converting to png."""
    convertable_formats = set(PNG_CONVERTABLE_FORMAT_STRS)
    format_strs |= PNG_CONVERTABLE_FORMAT_STRS
    file_formats = deepcopy(_PNG_CONVERTABLE_FILE_FORMATS)
    if TIFF_FORMAT_STR in format_strs:
        file_formats.add(TIFF_FILE_FORMAT)
        convertable_formats.add(TIFF_FORMAT_STR)
    convert_handlers[Png] = file_formats
    config[PROGRAM_NAME]["computed"]["convertable_formats"]["png"] = frozenset(
        convertable_formats
    )
    return format_strs


def _update_formats_webp_lossless(format_strs, convert_handlers, config):
    """Update formats if converting to webp lossless."""
    convertable_format_strs = set(WEBP_CONVERTABLE_FORMAT_STRS)
    format_strs |= WEBP_CONVERTABLE_FORMAT_STRS
    file_formats = deepcopy(_WEBP_CONVERTABLE_FILE_FORMATS)
    if TIFF_FORMAT_STR in format_strs:
        file_formats.add(TIFF_FILE_FORMAT)
        convertable_format_strs.add(TIFF_FORMAT_STR)
    convert_handlers[WebPLossless] = file_formats

    convert_handlers[Gif2WebP] = {
        Gif.OUTPUT_FILE_FORMAT,
        AnimatedGif.OUTPUT_FILE_FORMAT,
    }
    if TIFF_FORMAT_STR in format_strs:
        if WebPAnimatedLossless not in convert_handlers:
            convert_handlers[WebPAnimatedLossless] = set()
        convert_handlers[WebPAnimatedLossless].add(TIFF_ANIMATED_FILE_FORMAT)
    if Png.OUTPUT_FORMAT_STR in format_strs:
        if WebPAnimatedLossless not in convert_handlers:
            convert_handlers[WebPAnimatedLossless] = set()
        convert_handlers[WebPAnimatedLossless].add(PNG_ANIMATED_FILE_FORMAT)
    config[PROGRAM_NAME]["computed"]["convertable_formats"]["webp"] = frozenset(
        convertable_format_strs
    )
    return format_strs


def _update_formats_zip(format_strs, convert_handlers):
    """Update formats if converting to zip."""
    format_strs |= {Rar.INPUT_FORMAT_STR}
    convert_handlers[Rar] = {Rar.INPUT_FILE_FORMAT}
    return format_strs


def _update_formats_cbz(format_strs, convert_handlers):
    """Update formats if converting to cbz."""
    format_strs |= {CBR.INPUT_FORMAT_STR}
    convert_handlers[CBR] = {CBR.INPUT_FILE_FORMAT}
    return format_strs


def _update_formats(config: Configuration) -> dict:
    formats = _config_formats_list_to_set(config, "formats")
    if "extra_formats" in config[PROGRAM_NAME]["computed"]:
        extra_formats = _config_formats_list_to_set(
            config, "extra_formats", computed=True
        )
        config[PROGRAM_NAME]["computed"]["extra_formats"].set(sorted(extra_formats))
        formats |= extra_formats

    convert_to = _config_formats_list_to_set(config, "convert_to")
    config[PROGRAM_NAME]["convert_to"].set(sorted(convert_to))
    convert_handlers: dict[type[Handler], set[FileFormat]] = {}
    if Png.OUTPUT_FORMAT_STR in convert_to:
        formats = _update_formats_png(formats, convert_handlers, config)
    if WebPLossless.OUTPUT_FORMAT_STR in convert_to:
        formats = _update_formats_webp_lossless(formats, convert_handlers, config)
    if Rar.OUTPUT_FORMAT_STR in convert_to:
        formats = _update_formats_zip(formats, convert_handlers)
    if CBR.OUTPUT_FORMAT_STR in convert_to:
        formats = _update_formats_cbz(formats, convert_handlers)
    config[PROGRAM_NAME]["formats"].set(sorted(formats))

    return convert_handlers


def _create_format_handler_map(config: Configuration, convert_handlers: dict) -> None:
    """Create a format to handler map from config."""
    available_programs = _get_available_programs(config)
    format_handlers = {}
    format_strs = config[PROGRAM_NAME]["formats"].get(list)
    if not isinstance(format_strs, list):
        msg = f"wrong type for formats: {type(format_strs)}{format_strs}"
        raise TypeError(msg)
    format_strs = set(format_strs)

    for file_format, possible_file_handlers in _FORMAT_HANDLERS.items():
        if file_format.format_str not in format_strs:
            continue
        for (
            handler_type,
            possible_handler_classes,
        ) in possible_file_handlers.items():
            for handler_class in possible_handler_classes:
                available = handler_class.is_handler_available(
                    convert_handlers, available_programs, file_format
                )
                if available:
                    if file_format not in format_handlers:
                        format_handlers[file_format] = {}
                    format_handlers[file_format][handler_type] = handler_class
                    break
    config[PROGRAM_NAME]["computed"]["format_handlers"].set(format_handlers)
    config[PROGRAM_NAME]["computed"]["available_programs"].set(available_programs)


def _set_after(config) -> None:
    after = config[PROGRAM_NAME]["after"].get()
    if after is None:
        return

    try:
        timestamp = float(after)
    except ValueError:
        after_dt = parse(after)
        timestamp = time.mktime(after_dt.timetuple())

    config[PROGRAM_NAME]["after"].set(timestamp)


def _set_ignore(config) -> None:
    """Remove duplicates from the ignore list."""
    ignore: list[str] = config[PROGRAM_NAME]["ignore"].get(list)
    config[PROGRAM_NAME]["ignore"].set(tuple(sorted(set(ignore))))


def _set_timestamps(config) -> None:
    """Set the timestamps attribute."""
    timestamps = (
        config[PROGRAM_NAME]["timestamps"].get(bool)
        and not config[PROGRAM_NAME]["test"].get(bool)
        and not config[PROGRAM_NAME]["list_only"].get(bool)
    )
    config[PROGRAM_NAME]["timestamps"].set(timestamps)


def get_config(
    args: typing.Optional[Namespace] = None, modname=PROGRAM_NAME
) -> AttrDict:
    """Get the config dict, layering env and args over defaults."""
    config = Configuration(PROGRAM_NAME, modname=modname, read=False)
    config.read()
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
        msg = "Not a valid config"
        raise TypeError(msg)
    return ad.picopt
