"""Confuse config for picopt."""
import subprocess
import time
import typing

from argparse import Namespace
from datetime import datetime

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


_PNG_CONVERTABLE_FORMAT_OBJS = CONVERTABLE_FORMAT_OBJS | set(
    [Gif.OUTPUT_FORMAT_OBJ, TIFF_FORMAT_OBJ]
)
_WEBP_CONVERTABLE_FORMAT_OBJS = _PNG_CONVERTABLE_FORMAT_OBJS | set(
    [Png.OUTPUT_FORMAT_OBJ]
)
PNG_CONVERTABLE_FORMATS = set(
    [format.format for format in _PNG_CONVERTABLE_FORMAT_OBJS]
)
WEBP_CONVERTABLE_FORMATS = set(
    [format.format for format in _WEBP_CONVERTABLE_FORMAT_OBJS]
)
CONVERT_TO_FORMATS = set(
    (
        Png.OUTPUT_FORMAT,
        WebPLossless.OUTPUT_FORMAT,
        Zip.OUTPUT_FORMAT,
        CBZ.OUTPUT_FORMAT,
    )
)
CONTAINER_CONVERTABLE_FORMATS = set((Zip.INPUT_FORMAT_RAR, CBZ.INPUT_FORMAT_RAR))
DEFAULT_HANDLERS = (Gif, AnimatedGif, Jpeg, Png, WebPLossy, WebPLossless)
HANDLERS = set([*DEFAULT_HANDLERS, Gif2WebP, WebPAnimated, Zip, CBZ, EPub])
ALL_FORMATS: typing.Set[str] = (
    set([cls.OUTPUT_FORMAT for cls in HANDLERS])
    | CONVERTABLE_FORMATS
    | set([TIFF_FORMAT])
    | CONTAINER_CONVERTABLE_FORMATS
)
TEMPLATE = MappingTemplate(
    {
        "after": Optional(datetime),
        "bigger": bool,
        "convert_to": Optional(Sequence(Choice(CONVERT_TO_FORMATS))),
        "keep_metadata": bool,
        "follow_symlinks": bool,
        "formats": Sequence(Choice(ALL_FORMATS)),
        "ignore": Sequence(str),
        "jobs": Integer(),
        "list_only": bool,
        "paths": Sequence(Path()),
        "recurse": bool,
        "test": bool,
        "timestamps": bool,
        "verbose": Integer(),
        "_available_programs": set,
        "_extra_formats": Optional(Sequence(Choice(ALL_FORMATS))),
        "_format_handlers": dict,
    }
)
TIMESTAMPS_CONFIG_KEYS = (
    "bigger",
    "convert_to",
    "keep_metadata",
    "follow_symlinks",
    "formats",
    "ignore",
    "recurse",
)
# Handlers for formats are listed in priority order
FORMAT_HANDLERS = {
    PPM_FORMAT_OBJ: (WebPLossless, Png),
    BPM_FORMAT_OBJ: (WebPLossless, Png),
    Gif.OUTPUT_FORMAT_OBJ: (Gif2WebP, Png, Gif),
    AnimatedGif.OUTPUT_FORMAT_OBJ: (Gif2WebP, AnimatedGif),
    Jpeg.OUTPUT_FORMAT_OBJ: (Jpeg,),
    Png.OUTPUT_FORMAT_OBJ: (WebPLossless, Png),
    WebPLossy.OUTPUT_FORMAT_OBJ: (WebPLossy,),
    WebPLossless.OUTPUT_FORMAT_OBJ: (WebPLossless,),
    WebPAnimated.OUTPUT_FORMAT_OBJ: (WebPAnimated,),
    Zip.OUTPUT_FORMAT_OBJ: (Zip,),
    CBZ.OUTPUT_FORMAT_OBJ: (CBZ,),
    Zip.INPUT_FORMAT_OBJ_RAR: (Zip,),
    CBZ.INPUT_FORMAT_OBJ_RAR: (CBZ,),
    EPub.OUTPUT_FORMAT_OBJ: (EPub,),
    TIFF_FORMAT_OBJ: (WebPLossless, Png),
    TIFF_ANIMATED_FORMAT_OBJ: (WebPAnimated,),
}


def _does_external_program_run(prog: str, verbose: int) -> bool:
    """Test to see if the external programs can be run."""
    try:
        with open("/dev/null") as null:
            subprocess.call([prog, "-h"], stdout=null, stderr=null)
        result = True
    except OSError:
        if verbose > 1:
            print(f"couldn't run {prog}")
        result = False

    return result


def _get_available_programs(config: Configuration) -> set:
    """Run the external program tester on the required binaries."""
    verbose = config["verbose"].get(int)
    if not isinstance(verbose, int):
        raise ValueError(f"wrong type for covnert_to: {type(verbose)} {verbose}")
    programs = set()
    for handler in HANDLERS:
        for program in handler.PROGRAMS:
            if (
                program == Handler.INTERNAL
                or program.startswith("pil2")
                or _does_external_program_run(program, verbose)
            ):
                programs.add(program)
    if not programs:
        raise ValueError("No optimizers are available or all optimizers are disabled")
    return programs


def _config_list_to_set(config, key) -> typing.Set[str]:
    val_list = config[key].get(list)
    if not isinstance(val_list, (tuple, list, set)):
        raise ValueError(f"wrong type for convert_to: {type(val_list)} {val_list}")
    return set(val_list)


def _update_formats(config: Configuration) -> dict:
    convert_to = _config_list_to_set(config, "convert_to")
    formats = _config_list_to_set(config, "formats")
    if "_extra_formats" in config:
        formats |= _config_list_to_set(config, "_extra_formats")

    convert_handlers: typing.Dict[typing.Type[Handler], typing.Set[Format]] = {}
    if Png.OUTPUT_FORMAT in convert_to:
        formats |= PNG_CONVERTABLE_FORMATS
        convert_handlers[Png] = _PNG_CONVERTABLE_FORMAT_OBJS
        if TIFF_FORMAT in formats:
            convert_handlers[Png].add(TIFF_FORMAT_OBJ)
    if WebPLossless.OUTPUT_FORMAT in convert_to:
        formats |= WEBP_CONVERTABLE_FORMATS
        convert_handlers[WebPLossless] = _WEBP_CONVERTABLE_FORMAT_OBJS
        convert_handlers[Gif2WebP] = set(
            [Gif.OUTPUT_FORMAT_OBJ, AnimatedGif.OUTPUT_FORMAT_OBJ]
        )
        if TIFF_FORMAT in formats:
            convert_handlers[WebPLossless].add(TIFF_FORMAT_OBJ)
            convert_handlers[WebPAnimated] = set([TIFF_ANIMATED_FORMAT_OBJ])
    if Zip.OUTPUT_FORMAT in convert_to:
        formats |= set([Zip.INPUT_FORMAT_RAR])
        convert_handlers[Zip] = set([Zip.INPUT_FORMAT_OBJ_RAR])
    if CBZ.OUTPUT_FORMAT in convert_to:
        formats |= set([CBZ.INPUT_FORMAT_RAR])
        convert_handlers[CBZ] = set([CBZ.INPUT_FORMAT_OBJ_RAR])

    config["formats"].set(sorted(formats))
    return convert_handlers


def _create_format_handler_map(config: Configuration, convert_handlers: dict) -> None:
    """Create a format to handler map from config."""
    available_programs = _get_available_programs(config)
    format_handlers = {}
    formats = config["formats"].get(list)
    if not isinstance(formats, list):
        raise ValueError(f"wrong type for formats: {type(formats)}{formats}")
    formats = set(formats)

    for format, possible_handler_classes in FORMAT_HANDLERS.items():
        for handler_class in possible_handler_classes:
            if format.format in formats and handler_class.is_handler_available(
                convert_handlers, available_programs, format
            ):
                format_handlers[format] = handler_class
                break

    config["_format_handlers"].set(format_handlers)
    config["_available_programs"].set(available_programs)


def _set_after(config) -> None:
    after = config["after"].get()
    if after is None:
        return

    if isinstance(after, str):
        after_dt = parse(after)
        timestamp = time.mktime(after_dt.timetuple())
    elif isinstance(after, int) or isinstance(after, float):
        timestamp = float(after)
    else:
        timestamp = None
    config["after"].set(timestamp)


def _set_ignore(config) -> None:
    """Remove duplicates from the ignore list."""
    ignore_list: typing.List[str] = config["ignore"].get(list)
    config["ignore"].set(tuple(sorted(set(ignore_list))))


def _set_timestamps(config) -> None:
    """Set the timestamps attribute."""
    timestamps = (
        config["timestamps"].get(bool)
        and not config["test"].get(bool)
        and not config["list_only"].get(bool)
    )
    config["timestamps"].set(timestamps)


def get_config(args: typing.Optional[Namespace] = None) -> AttrDict:
    """Get the config dict, layering env and args over defaults."""
    config = Configuration(PROGRAM_NAME, PROGRAM_NAME)
    if args and args.config:
        config.set_file(args.config)
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
    return ad
