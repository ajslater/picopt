"""Contst and Confuse Config template."""

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

CONVERT_TO_FORMAT_STRS = frozenset(
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
    {
        cls.INPUT_FORMAT_STR
        for cls in (Rar, Cbr, SevenZip, Cb7, Tar, TarGz, TarBz, TarXz, Cbt)
    }
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
