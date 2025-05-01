"""Contst and Confuse Config template."""

from picopt.formats import (
    LOSSLESS_FORMAT_STRS,
    MPO_FILE_FORMAT,
)
from picopt.handlers.container.animated.webp import WebPAnimatedLossless
from picopt.handlers.container.archive.rar import (
    Cbr,
    Rar,
)
from picopt.handlers.container.archive.seven_zip import (
    Cb7,
    SevenZip,
)
from picopt.handlers.container.archive.tar import (
    Cbt,
    Tar,
    TarBz,
    TarGz,
    TarXz,
)
from picopt.handlers.container.archive.zip import (
    Cbz,
    EPub,
    Zip,
)
from picopt.handlers.image.gif import Gif, GifAnimated
from picopt.handlers.image.jpeg import Jpeg
from picopt.handlers.image.png import Png, PngAnimated
from picopt.handlers.image.svg import Svg
from picopt.handlers.image.webp import WebPLossless

_LOSSLESS_IMAGE_CONVERT_TO_HANDLERS = (
    Png,
    PngAnimated,
    WebPLossless,
    WebPAnimatedLossless,
)

LOSSLESS_IMAGE_CONVERT_TO_FORMAT_STRS = frozenset(
    {cls.OUTPUT_FORMAT_STR for cls in _LOSSLESS_IMAGE_CONVERT_TO_HANDLERS}
)
_OTHER_CONVERT_TO_HANDLERS = (
    Zip,
    Cbz,
    Jpeg,
)

CONVERT_TO_FORMAT_STRS = frozenset(
    {cls.OUTPUT_FORMAT_STR for cls in _OTHER_CONVERT_TO_HANDLERS}
    | LOSSLESS_IMAGE_CONVERT_TO_FORMAT_STRS
)
ARCHIVE_CONVERT_FROM_FORMAT_STRS = tuple(
    sorted({cls.INPUT_FORMAT_STR for cls in (Rar, SevenZip, Tar, TarGz, TarBz, TarXz)})
)
CB_CONVERT_FROM_FORMAT_STRS = tuple(
    sorted({cls.INPUT_FORMAT_STR for cls in (Cbr, Cb7, Cbt)})
)

_ARCHIVE_CONVERTIBLE_FORMAT_STRS = frozenset(
    ARCHIVE_CONVERT_FROM_FORMAT_STRS + CB_CONVERT_FROM_FORMAT_STRS
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
_INPUT_ONLY_HANDLERS = frozenset({Rar, Cbr})
_HANDLER_OUTPUT_FORMAT_STRS = frozenset(
    [cls.OUTPUT_FORMAT_STR for cls in _ALL_HANDLERS - _INPUT_ONLY_HANDLERS]
)
ALL_FORMAT_STRS: frozenset[str] = (
    _HANDLER_OUTPUT_FORMAT_STRS
    | _ARCHIVE_CONVERTIBLE_FORMAT_STRS
    | LOSSLESS_FORMAT_STRS
    | {MPO_FILE_FORMAT.format_str}
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
