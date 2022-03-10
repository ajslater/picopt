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
    MappingValues,
    Optional,
    Path,
    Sequence,
)
from dateutil.parser import parse

from picopt import PROGRAM_NAME
from picopt.handlers.container import ContainerHandler
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
DEFAULT_HANDLERS = (Gif, AnimatedGif, Jpeg, Png, WebPLossy, WebPLossless)
HANDLERS = set([*DEFAULT_HANDLERS, Gif2WebP, WebPAnimated, Zip, CBZ, EPub])
ALL_FORMATS: typing.Set[str] = (
    set([cls.OUTPUT_FORMAT for cls in HANDLERS])
    | CONVERTABLE_FORMATS
    | set([TIFF_FORMAT])
)
TEMPLATE = MappingTemplate(
    {
        "after": Optional(datetime),
        "bigger": bool,
        "convert_to": MappingValues(bool),
        "keep_metadata": bool,
        "follow_symlinks": bool,
        "formats": set,
        "jobs": Integer(),
        "list_only": bool,
        "paths": Sequence(Path()),
        "record_timestamp": bool,
        "recurse": bool,
        "test": bool,
        "verbose": Integer(),
        "_available_programs": set,
        "_extra_formats": Optional(Sequence(Choice(ALL_FORMATS))),
        "_format_handlers": dict,
    }
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


def _get_available_programs(config) -> set:
    """Run the external program tester on the required binaries."""
    programs = set()
    for handler in HANDLERS:
        for program in handler.PROGRAMS:
            if (
                program == Handler.INTERNAL
                or program.startswith("pil2")
                or _does_external_program_run(program, config["verbose"].get(int))
            ):
                programs.add(program)
    if not programs:
        raise ValueError("No optimizers are available or all optimizers are disabled")
    return programs


def _update_formats(config) -> dict:
    convert_to: typing.Dict[str, bool] = config["convert_to"].get(dict)
    formats: typing.Set[str] = set(config["formats"].get(set))
    convert_handlers: typing.Dict[typing.Type[Handler], typing.Set[Format]] = {}
    if "_extra_formats" in config:
        formats |= set(config["_extra_formats"].get(list))
    if convert_to.get(Png.OUTPUT_FORMAT):
        formats |= PNG_CONVERTABLE_FORMATS
        convert_handlers[Png] = _PNG_CONVERTABLE_FORMAT_OBJS
        if TIFF_FORMAT in formats:
            convert_handlers[Png].add(TIFF_FORMAT_OBJ)
    if convert_to.get(WebPLossless.OUTPUT_FORMAT):
        formats |= WEBP_CONVERTABLE_FORMATS
        convert_handlers[WebPLossless] = _WEBP_CONVERTABLE_FORMAT_OBJS
        convert_handlers[Gif2WebP] = set(
            [Gif.OUTPUT_FORMAT_OBJ, AnimatedGif.OUTPUT_FORMAT_OBJ]
        )
        if TIFF_FORMAT in formats:
            convert_handlers[WebPLossless].add(TIFF_FORMAT_OBJ)
            convert_handlers[WebPAnimated] = set([TIFF_ANIMATED_FORMAT_OBJ])
    if convert_to.get(Zip.OUTPUT_FORMAT):
        formats |= set([Zip.INPUT_FORMAT_RAR])
        convert_handlers[Zip] = set([Zip.INPUT_FORMAT_OBJ_RAR])
    if convert_to.get(CBZ.OUTPUT_FORMAT):
        formats |= set([CBZ.INPUT_FORMAT_RAR])
        convert_handlers[CBZ] = set([CBZ.INPUT_FORMAT_OBJ_RAR])

    config["formats"].set(set(formats))
    return convert_handlers


def _create_format_handler_map(config: Configuration, convert_handlers: dict) -> None:
    """Create a format to handler map from config."""
    available_programs = _get_available_programs(config)
    format_handlers = {}
    formats = config["formats"].get(set)
    if not isinstance(formats, set):
        raise ValueError(f"wrong type for formats: {type(formats)}{formats}")
    recurse = bool(config["recurse"].get(bool))

    for format, possible_handler_classes in FORMAT_HANDLERS.items():
        for handler_class in possible_handler_classes:
            if format.format in formats and handler_class.is_handler_available(
                convert_handlers, available_programs, format
            ):
                format_handlers[format] = handler_class
                recurse |= issubclass(handler_class, ContainerHandler)
                break

    config["recurse"].set(recurse)
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
    ad = config.get(TEMPLATE)
    if not isinstance(ad, AttrDict):
        raise ValueError()
    return ad
