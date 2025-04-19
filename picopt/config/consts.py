"""Contst and Confuse Config template."""

from confuse.templates import (
    Choice,
    Integer,
    MappingTemplate,
    Optional,
    Sequence,
)
from confuse.templates import Path as ConfusePath

from picopt import PROGRAM_NAME
from picopt.formats import (
    LOSSLESS_FORMAT_STRS,
    MPO_FILE_FORMAT,
)
from picopt.handlers.archive.rar import (
    Cbr,
    Rar,
)
from picopt.handlers.archive.seven_zip import (
    Cb7,
    SevenZip,
)
from picopt.handlers.archive.tar import (
    Cbt,
    Tar,
    TarBz,
    TarGz,
    TarXz,
)
from picopt.handlers.archive.zip import (
    Cbz,
    EPub,
    Zip,
)
from picopt.handlers.image.gif import Gif, GifAnimated
from picopt.handlers.image.jpeg import Jpeg
from picopt.handlers.image.png import Png, PngAnimated
from picopt.handlers.image.svg import Svg
from picopt.handlers.image.webp import WebPAnimatedLossless, WebPLossless

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
_TEMPORARILY_CONVERT_ONLY = (SevenZip, Cb7, Tar, TarGz, TarBz, TarXz)
_CONTAINER_CONVERTIBLE_FORMAT_STRS = frozenset(
    {cls.INPUT_FORMAT_STR for cls in (Rar, Cbr, Cbt, *_TEMPORARILY_CONVERT_ONLY)}
)

DEFAULT_HANDLERS = frozenset(
    {Gif, GifAnimated, Jpeg, Png, WebPLossless, WebPAnimatedLossless}
)
_NON_PIL_HANDLERS = frozenset({Svg})
_ARCHIVE_HANDLERS = frozenset(
    {
        Zip,
        Cbz,
        EPub,
        Rar,
        Cbr,
        SevenZip,
        Cb7,
        Tar,
        TarGz,
        TarBz,
        TarXz,
        Cbt,
    }
)
_ALL_HANDLERS = frozenset(DEFAULT_HANDLERS | _NON_PIL_HANDLERS | _ARCHIVE_HANDLERS)
ALL_FORMAT_STRS: frozenset[str] = (
    frozenset([cls.OUTPUT_FORMAT_STR for cls in _ALL_HANDLERS])
    | LOSSLESS_FORMAT_STRS
    | _CONTAINER_CONVERTIBLE_FORMAT_STRS
    | {str(MPO_FILE_FORMAT.format_str)}
)
TEMPLATE = MappingTemplate(
    {
        PROGRAM_NAME: MappingTemplate(
            {
                "after": Optional(float),
                "bigger": bool,
                "convert_to": Optional(Sequence(Choice(_CONVERT_TO_FORMAT_STRS))),
                "disable_programs": Sequence(str),
                "dry_run": bool,
                "extra_formats": Optional(Sequence(Choice(ALL_FORMAT_STRS))),
                "formats": Sequence(Choice(ALL_FORMAT_STRS)),
                "ignore": Sequence(str),
                "jobs": Integer(),
                "keep_metadata": bool,
                "list_only": bool,
                "near_lossless": bool,
                "paths": Sequence(ConfusePath()),
                "png_max": bool,
                "preserve": bool,
                "recurse": bool,
                "symlinks": bool,
                "timestamps": bool,
                "timestamps_check_config": bool,
                "verbose": Integer(),
                "computed": Optional(
                    MappingTemplate(
                        {
                            "native_handlers": dict,
                            "convert_handlers": dict,
                            "handler_stages": dict,
                            "is_modern_cwebp": bool,
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
# cwebp before this version only accepts PNG & WEBP
MIN_CWEBP_VERSION = (1, 2, 3)
