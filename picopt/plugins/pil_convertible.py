"""
PIL-convertible-formats plugin.

This plugin owns no handlers of its own. It is a collection bag that
contributes :class:`Route` entries from every PIL-readable format that
picopt knows how to convert into a "real" target format owned by another
plugin (PNG, WebPLossless, the animated WebP handlers).

Why this exists as a separate plugin and not as routes added directly to
each target plugin: the source-format list is long (≈18 entries), it
spans both still and animated, and it's the natural seam where future
formats (HEIF, AVIF) will get added. Keeping it in one file means the
PNG plugin doesn't have to know about Spider or QOI, and the WebP plugin
doesn't have to know about FITS.

Also owns the TIFF lossless-compression check. The future
:mod:`picopt.walk.detect_format` rewrite imports :func:`is_tiff_lossless`
and calls it during PIL inspection of TIFF inputs to decide whether the
file is a lossless candidate or should be skipped.

This plugin is ``default_enabled=False`` — these are conversions, not
native formats, and the user opts in via ``--convert-to``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PIL.BmpImagePlugin import BmpImageFile, DibImageFile
from PIL.CurImagePlugin import CurImageFile
from PIL.FitsImagePlugin import FitsImageFile
from PIL.FliImagePlugin import FliImageFile
from PIL.ImtImagePlugin import ImtImageFile
from PIL.PcxImagePlugin import PcxImageFile
from PIL.PixarImagePlugin import PixarImageFile
from PIL.PpmImagePlugin import PpmImageFile
from PIL.PsdImagePlugin import PsdImageFile
from PIL.QoiImagePlugin import QoiImageFile
from PIL.SgiImagePlugin import SgiImageFile
from PIL.SpiderImagePlugin import SpiderImageFile
from PIL.SunImagePlugin import SunImageFile
from PIL.TgaImagePlugin import TgaImageFile
from PIL.TiffImagePlugin import TiffImageFile
from PIL.XbmImagePlugin import XbmImageFile
from PIL.XpmImagePlugin import XpmImageFile

from picopt.plugins.base import Plugin, Route
from picopt.plugins.base.format import FileFormat
from picopt.plugins.png import Png, PngAnimated
from picopt.plugins.webp import (
    Img2WebPAnimatedLossless,
    PILPackWebPAnimatedLossless,
    WebPLossless,
)

if TYPE_CHECKING:
    from PIL.Image import Image

# ---------------------------------------------------------------------------
# TIFF lossless compression check
# ---------------------------------------------------------------------------

# Compression names PIL exposes via Image.info["compression"] for TIFF
# inputs that we consider losslessly recompressible. None covers
# uncompressed TIFFs that don't set the key at all. Anything not in this
# set (LZW with quality loss, JPEG-in-TIFF, etc.) means picopt should
# skip the file rather than risk a lossy round-trip.
TIFF_LOSSLESS_COMPRESSION: frozenset[str | None] = frozenset(
    {
        None,
        "group3",
        "group4",
        "lzma",
        "packbits",
        "tiff_adobe_deflate",
        "tiff_ccitt",
        "tiff_lzw",
        "tiff_raw_16",
        "tiff_sgilog",
        "tiff_sgilog24",
        "tiff_thunderscan",
        "zstd",
    }
)


def is_tiff_lossless(info: dict[str, Any]) -> bool:
    """
    Return True if a TIFF's PIL ``info`` dict reports a lossless codec.

    Hook used by the (future) PIL-based detector to decide whether a TIFF
    input is a candidate for picopt's lossless-recompression pipeline.
    """
    return info.get("compression") in TIFF_LOSSLESS_COMPRESSION


# ---------------------------------------------------------------------------
# Format-string lists
# ---------------------------------------------------------------------------

# Still images: PIL formats that picopt can convert to PNG or WebPLossless.
# Excludes MpoImageFile because the JPEG plugin already owns the MPO route
# (MPO is conceptually a JPEG container).
_STILL_PIL_FORMATS: tuple[type[Image], ...] = (
    # Read/write losslessly:
    BmpImageFile,
    DibImageFile,
    PcxImageFile,
    PpmImageFile,
    SgiImageFile,
    SpiderImageFile,
    TgaImageFile,
    TiffImageFile,
    XbmImageFile,
    # Read only:
    CurImageFile,
    FitsImageFile,
    ImtImageFile,
    PixarImageFile,
    PsdImageFile,
    SunImageFile,
    XpmImageFile,
    QoiImageFile,
)

# Animated PIL formats. GIF and PNG are owned by their own plugins.
_ANIMATED_PIL_FORMATS: tuple[type[Image], ...] = (
    FliImageFile,
    TiffImageFile,  # multipage TIFF reads as animated
)


def _file_format(image_class, *, animated: bool) -> FileFormat:
    return FileFormat(str(image_class.format), lossless=True, animated=animated)


_STILL_FILE_FORMATS: tuple[FileFormat, ...] = tuple(
    _file_format(c, animated=False) for c in _STILL_PIL_FORMATS
)
_ANIMATED_FILE_FORMATS: tuple[FileFormat, ...] = tuple(
    _file_format(c, animated=True) for c in _ANIMATED_PIL_FORMATS
)


# ---------------------------------------------------------------------------
# Route construction
# ---------------------------------------------------------------------------

# Convert targets for still PIL inputs, in preference order.
# WebPLossless wins because lossless WebP usually beats lossless PNG on
# size for natural images; Png is the fallback when the user has WebP
# disabled.
_STILL_CONVERT_TARGETS = (WebPLossless, Png)

# Convert targets for animated PIL inputs (FLI, multipage TIFF, …).
# webpmux is intentionally absent because it can only read existing
# animated WebP, and PngAnimated is included as a non-WebP fallback.
_ANIMATED_CONVERT_TARGETS = (
    Img2WebPAnimatedLossless,
    PILPackWebPAnimatedLossless,
    PngAnimated,
)


_ROUTES: tuple[Route, ...] = (
    *(
        Route(file_format=ff, convert=_STILL_CONVERT_TARGETS)
        for ff in _STILL_FILE_FORMATS
    ),
    *(
        Route(file_format=ff, convert=_ANIMATED_CONVERT_TARGETS)
        for ff in _ANIMATED_FILE_FORMATS
    ),
)


# Every format string the registry should know about as a possible input.
_EXTRA_FORMAT_STRS: frozenset[str] = frozenset(
    {ff.format_str for ff in (*_STILL_FILE_FORMATS, *_ANIMATED_FILE_FORMATS)}
)


PLUGIN = Plugin(
    name="PIL_CONVERTIBLE",
    handlers=(),
    routes=_ROUTES,
    convert_targets=(),
    default_enabled=False,
    extra_format_strs=_EXTRA_FORMAT_STRS,
)
