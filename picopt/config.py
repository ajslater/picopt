"""Confuse config for picopt."""
import pathlib
import stat
import time
from argparse import Namespace
from collections.abc import ItemsView
from dataclasses import dataclass, fields
from types import MappingProxyType

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
from picopt.handlers.convertible import (
    APNG_FILE_FORMAT,
    CONVERTABLE_ANIMATED_FILE_FORMATS,
    CONVERTABLE_ANIMATED_FORMAT_STRS,
    CONVERTABLE_FILE_FORMATS,
    CONVERTABLE_FORMAT_STRS,
    GIF_FORMAT_STR,
    PNG_FORMAT_STR,
    TIFF_FORMAT_STR,
)
from picopt.handlers.gif import Gif, GifAnimated
from picopt.handlers.handler import FileFormat, Handler
from picopt.handlers.jpeg import Jpeg
from picopt.handlers.png import Png
from picopt.handlers.svg import SVG
from picopt.handlers.webp import Gif2WebP, WebPLossless
from picopt.handlers.webp_animated import WebPAnimatedLossless
from picopt.handlers.zip import CBR, CBZ, EPub, Rar, Zip

# TODO move CONVERTIBLE FORMAT STRS into convertible wherever it ends up
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
DEFAULT_HANDLERS = frozenset({Gif, GifAnimated, Jpeg, Png, SVG, WebPLossless})
HANDLERS = frozenset(
    DEFAULT_HANDLERS
    | {
        Gif2WebP,
        WebPAnimatedLossless,
        Zip,
        Rar,
        CBZ,
        CBR,
        EPub,
    }
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
                "converge": bool,
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

    convert: tuple[type[Handler], ...] = ()
    native: tuple[type[Handler], ...] = ()

    def items(self) -> ItemsView[str, tuple[type[Handler], ...]]:
        """Return both fields."""
        return MappingProxyType(
            {field.name: tuple(getattr(self, field.name)) for field in fields(self)}
        ).items()


# Handlers for formats are listed in priority order
_LOSSLESS_CONVERTABLE_FORMAT_HANDLERS = MappingProxyType(
    {
        ffmt: FileFormatHandlers(convert=(WebPLossless, Png))
        for ffmt in CONVERTABLE_FILE_FORMATS
    }
)
_LOSSLESS_CONVERTABLE_ANIMATED_FORMAT_HANDLERS = MappingProxyType(
    {
        ffmt: FileFormatHandlers(convert=(WebPAnimatedLossless,))
        for ffmt in CONVERTABLE_ANIMATED_FILE_FORMATS
    }
)
_FORMAT_HANDLERS = MappingProxyType(
    {
        **_LOSSLESS_CONVERTABLE_FORMAT_HANDLERS,
        **_LOSSLESS_CONVERTABLE_ANIMATED_FORMAT_HANDLERS,
        Gif.OUTPUT_FILE_FORMAT: FileFormatHandlers(
            convert=(Gif2WebP, Png), native=(Gif,)
        ),
        GifAnimated.OUTPUT_FILE_FORMAT: FileFormatHandlers(
            convert=(Gif2WebP,), native=(GifAnimated,)
        ),
        Jpeg.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(Jpeg,)),
        Png.OUTPUT_FILE_FORMAT: FileFormatHandlers(
            convert=(WebPLossless,), native=(Png,)
        ),
        APNG_FILE_FORMAT: FileFormatHandlers(convert=(WebPAnimatedLossless,)),
        WebPLossless.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(WebPLossless,)),
        WebPAnimatedLossless.OUTPUT_FILE_FORMAT: FileFormatHandlers(
            native=(WebPAnimatedLossless,)
        ),
        Zip.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(Zip,)),
        CBZ.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(CBZ,)),
        Rar.INPUT_FILE_FORMAT: FileFormatHandlers(convert=(Rar,)),
        CBR.INPUT_FILE_FORMAT: FileFormatHandlers(convert=(CBR,)),
        EPub.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(EPub,)),
        SVG.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(SVG,)),
    }
)
MODE_EXECUTABLE = stat.S_IXUSR ^ stat.S_IXGRP ^ stat.S_IXOTH


def _is_external_program_executable(
    program: str, bin_path: str | tuple[str, ...] | None, verbose: int
) -> bool:
    """Test to see if the external programs can be run."""
    try:
        if not bin_path:
            return False
        test_path = bin_path[0] if isinstance(bin_path, tuple) else bin_path
        path = pathlib.Path(test_path)
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


def _set_all_format_strs(config) -> frozenset[str]:
    all_format_strs = _config_formats_list_to_set(config, "formats")
    if "extra_formats" in config[PROGRAM_NAME]["computed"]:
        extra_format_strs = _config_formats_list_to_set(
            config, "extra_formats", computed=True
        )
        config[PROGRAM_NAME]["computed"]["extra_formats"].set(sorted(extra_format_strs))
        all_format_strs |= extra_format_strs

    config[PROGRAM_NAME]["formats"].set(sorted(all_format_strs))
    return frozenset(all_format_strs)


def _set_convert_handlers_png(convert_to, all_format_strs, convert_handlers, config):
    if Png.OUTPUT_FORMAT_STR not in convert_to:
        return
    convert_handlers_png_lossless = set()
    for fmt in frozenset(CONVERTABLE_FILE_FORMATS | {Gif.OUTPUT_FILE_FORMAT}):
        if fmt.format_str in all_format_strs:
            convert_handlers_png_lossless.add(fmt)

    convert_handlers[Png] = frozenset(convert_handlers_png_lossless)

    config[PROGRAM_NAME]["computed"]["convertable_formats"]["png"] = frozenset(
        frozenset(CONVERTABLE_FORMAT_STRS | {GIF_FORMAT_STR}) & all_format_strs
    )


def _set_convert_handlers_webp(convert_to, all_format_strs, convert_handlers, config):
    if WebPLossless.OUTPUT_FORMAT_STR not in convert_to:
        return

    if Gif.OUTPUT_FORMAT_STR in all_format_strs:
        convert_handlers[Gif2WebP] = frozenset(
            {
                Gif.OUTPUT_FILE_FORMAT,
                GifAnimated.OUTPUT_FILE_FORMAT,
            }
        )

    convert_handlers_webp_lossless = set()
    convert_handlers_webp_animated_lossless = set()
    if Png.OUTPUT_FORMAT_STR in all_format_strs:
        convert_handlers_webp_lossless.add(Png.OUTPUT_FILE_FORMAT)
        convert_handlers_webp_animated_lossless.add(APNG_FILE_FORMAT)

    for fmt in CONVERTABLE_FILE_FORMATS:
        if fmt.format_str in all_format_strs:
            convert_handlers_webp_lossless.add(fmt)

    for fmt in CONVERTABLE_ANIMATED_FILE_FORMATS:
        if fmt.format_str in all_format_strs:
            convert_handlers_webp_animated_lossless.add(fmt)

    convert_handlers[WebPLossless] = frozenset(convert_handlers_webp_lossless)
    convert_handlers[WebPAnimatedLossless] = frozenset(
        convert_handlers_webp_animated_lossless
    )

    config[PROGRAM_NAME]["computed"]["convertable_formats"]["webp"] = frozenset(
        frozenset(
            CONVERTABLE_FORMAT_STRS
            | CONVERTABLE_ANIMATED_FORMAT_STRS
            | {GIF_FORMAT_STR, PNG_FORMAT_STR}
        )
        & all_format_strs
    )


def _set_convert_handlers_rar(convert_to, all_format_strs, convert_handlers, config):
    if (
        Zip.OUTPUT_FORMAT_STR not in convert_to
        or Rar.INPUT_FORMAT_STR not in all_format_strs
    ):
        return
    convert_handlers[Rar] = frozenset({Rar.INPUT_FILE_FORMAT})
    config[PROGRAM_NAME]["computed"]["convertable_formats"]["zip"] = frozenset(
        {Rar.INPUT_FORMAT_STR}
    )


def _set_convert_handlers_cbr(convert_to, all_format_strs, convert_handlers, config):
    if (
        CBZ.OUTPUT_FORMAT_STR not in convert_to
        or CBR.INPUT_FORMAT_STR not in all_format_strs
    ):
        return
    convert_handlers[CBR] = frozenset({CBR.INPUT_FILE_FORMAT})
    config[PROGRAM_NAME]["computed"]["convertable_formats"]["cbz"] = frozenset(
        {CBR.INPUT_FORMAT_STR}
    )


def _set_convert_formats(
    config: Configuration, all_format_strs: frozenset, convert_to: frozenset
) -> MappingProxyType:
    """Set formats in config and return convert handlers."""
    convert_handlers: dict[type[Handler], frozenset[FileFormat]] = {}

    _set_convert_handlers_png(convert_to, all_format_strs, convert_handlers, config)
    _set_convert_handlers_webp(convert_to, all_format_strs, convert_handlers, config)
    # TODO TAR CONVERSION
    _set_convert_handlers_rar(convert_to, all_format_strs, convert_handlers, config)
    _set_convert_handlers_cbr(convert_to, all_format_strs, convert_handlers, config)

    return MappingProxyType(convert_handlers)


def _create_format_handler_map(
    config: Configuration,
) -> None:
    """Create a format to handler map from config."""
    all_format_strs = _set_all_format_strs(config)

    available_programs = _get_available_programs(config)
    config[PROGRAM_NAME]["computed"]["available_programs"].set(available_programs)
    # TODO if no way to convert_to, abort

    convert_to = _config_formats_list_to_set(config, "convert_to")
    config[PROGRAM_NAME]["convert_to"].set(sorted(convert_to))

    convert_handlers = _set_convert_formats(config, all_format_strs, convert_to)

    format_handlers = {}
    for file_format, possible_file_handlers in _FORMAT_HANDLERS.items():
        if file_format.format_str not in all_format_strs:
            continue
        for (
            handler_type,
            possible_handler_classes,
        ) in possible_file_handlers.items():
            for handler_class in possible_handler_classes:
                available = handler_class.is_handler_available(
                    convert_handlers, available_programs, file_format
                )
                if not available:
                    continue
                if (
                    handler_type == "convert"
                    and handler_class.OUTPUT_FILE_FORMAT.format_str not in convert_to
                ):
                    continue
                if file_format not in format_handlers:
                    format_handlers[file_format] = {}
                format_handlers[file_format][handler_type] = handler_class
                break

    # TODO if no format handler adjust config.formats
    config[PROGRAM_NAME]["computed"]["format_handlers"].set(format_handlers)


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


def get_config(args: Namespace | None = None, modname=PROGRAM_NAME) -> AttrDict:
    """Get the config dict, layering env and args over defaults."""
    config = Configuration(PROGRAM_NAME, modname=modname, read=False)
    config.read()
    if args and args.picopt and args.picopt.config:
        config.set_file(args.picopt.config)
    config.set_env()
    if args:
        config.set_args(args)
    _set_after(config)
    _create_format_handler_map(config)
    _set_ignore(config)
    _set_timestamps(config)
    ad = config.get(TEMPLATE)
    if not isinstance(ad, AttrDict):
        msg = "Not a valid config"
        raise TypeError(msg)
    return ad.picopt
