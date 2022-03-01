"""Confuse config for picopt."""
import subprocess
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

from picopt import PROGRAM_NAME
from picopt.handlers.gif import Gif
from picopt.handlers.handler import Format, Handler
from picopt.handlers.image import (
    BPM_FORMAT,
    CONVERTABLE_FORMAT_STRS,
    CONVERTABLE_FORMATS,
    PPM_FORMAT,
)
from picopt.handlers.jpeg import Jpeg
from picopt.handlers.png import Png
from picopt.handlers.webp import Gif2WebP, WebPLossless, WebPLossy
from picopt.handlers.webp_animated import WebPAnimated
from picopt.handlers.zip import CBZ, Zip
from picopt.timestamp import Timestamp


_PNG_CONVERTABLE_FORMATS = CONVERTABLE_FORMATS | set([Gif.FORMAT])
_WEBP_CONVERTABLE_FORMATS = _PNG_CONVERTABLE_FORMATS | set([Png.FORMAT])
PNG_CONVERTABLE_FORMAT_STRS = set(
    [format.format for format in _PNG_CONVERTABLE_FORMATS]
)
WEBP_CONVERTABLE_FORMAT_STRS = set(
    [format.format for format in _WEBP_CONVERTABLE_FORMATS]
)
HANDLERS = set((WebPLossless, WebPLossy, Gif2WebP, Png, Jpeg, Gif, Zip, CBZ))
ALL_FORMAT_STRS: typing.Set[str] = (
    set([cls.FORMAT_STR for cls in HANDLERS]) | CONVERTABLE_FORMAT_STRS
)


TEMPLATE = MappingTemplate(
    {
        "after": Optional(datetime),
        "bigger": bool,
        "convert_to": MappingValues(bool),
        "destroy_metadata": bool,
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
        "_extra_formats": Optional(Sequence(Choice(ALL_FORMAT_STRS))),
        "_format_handlers": dict,
    }
)
HANDLERS = set(
    [Gif, Jpeg, Png, WebPLossless, WebPLossy, Gif2WebP, WebPAnimated, Zip, CBZ]
)
# Handlers for formats are listed in priority order
FORMAT_HANDLERS = {
    PPM_FORMAT: (WebPLossless, Png),
    BPM_FORMAT: (WebPLossless, Png),
    Gif.FORMAT: (Gif2WebP, Png, Gif),
    Gif.FORMAT_ANIMATED: (Gif2WebP, Gif),
    Jpeg.FORMAT: (Jpeg,),
    Png.FORMAT: (WebPLossless, Png),
    WebPLossy.FORMAT: (WebPLossy,),
    WebPLossless.FORMAT: (WebPLossless,),
    WebPAnimated.FORMAT: (WebPAnimated,),
    Zip.FORMAT: (Zip,),
    CBZ.FORMAT: (CBZ,),
    Zip.RAR_FORMAT: (Zip,),
    CBZ.RAR_FORMAT: (CBZ,),
}

_DEFAULT_HANDLERS = (Gif, Jpeg, Png, WebPLossy, WebPLossless)
DEFAULT_FORMAT_STRS = set([handler.FORMAT_STR for handler in _DEFAULT_HANDLERS])


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
            if program.startswith("pil2") or _does_external_program_run(
                program, config["verbose"].get(int)
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
    if convert_to.get(Png.FORMAT_STR):
        formats |= PNG_CONVERTABLE_FORMAT_STRS
        convert_handlers[Png] = _PNG_CONVERTABLE_FORMATS
    if convert_to.get(WebPLossless.FORMAT_STR):
        formats |= WEBP_CONVERTABLE_FORMAT_STRS
        convert_handlers[WebPLossless] = _WEBP_CONVERTABLE_FORMATS
        convert_handlers[Gif2WebP] = Gif.NATIVE_FORMATS
    if convert_to.get(Zip.FORMAT_STR):
        formats |= set([Zip.RAR_FORMAT_STR])
        convert_handlers[Zip] = set([Zip.RAR_FORMAT])
    if convert_to.get(CBZ.FORMAT_STR):
        formats |= set([CBZ.RAR_FORMAT_STR])
        convert_handlers[CBZ] = set([CBZ.RAR_FORMAT])

    config["formats"].set(set(formats))
    return convert_handlers


def _create_format_handler_map(config: Configuration, convert_handlers: dict) -> None:
    """Create a format to handler map from config."""
    available_programs = _get_available_programs(config)
    format_handlers = {}
    formats = config["formats"].get(set)
    if not isinstance(formats, set):
        raise ValueError(f"wrong type for formats: {type(formats)}{formats}")
    recurse = config["recurse"].get(bool)

    for format, possible_handler_classes in FORMAT_HANDLERS.items():
        for handler_class in possible_handler_classes:
            if handler_class.is_handler_available(
                formats, convert_handlers, available_programs, format
            ):
                format_handlers[format] = handler_class
                recurse |= handler_class.IMPLIES_RECURSE
                break

    config["recurse"].set(recurse)
    config["_format_handlers"].set(format_handlers)
    config["_available_programs"].set(available_programs)


def _set_after(config) -> None:
    after = config["after"].get()
    if after is None:
        return

    if isinstance(after, str):
        timestamp = Timestamp.parse_date_string(after)
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
