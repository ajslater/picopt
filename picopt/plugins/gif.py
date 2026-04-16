"""
GIF format plugin.

Owns: GIF (still + animated). Tool: gifsicle (external).
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, BinaryIO

from PIL.GifImagePlugin import GifImageFile
from typing_extensions import override

from picopt.plugins.base import (
    ExternalTool,
    Handler,
    ImageHandler,
    Plugin,
    Route,
    Tool,
)
from picopt.plugins.base.format import FileFormat

if TYPE_CHECKING:
    from io import BytesIO

# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

_GIFSICLE_ARGS: tuple[str, ...] = (
    "--optimize=3",
    "--threads",
    "--output",
    "-",
    "-",
)


class GifsicleTool(ExternalTool):
    """gifsicle external optimizer."""

    name = "gifsicle"
    binary = "gifsicle"

    @override
    def parse_version(self: GifsicleTool, version: str) -> str:
        version = super().parse_version(version)
        return version.split()[-1]

    @override
    def run_stage(self, handler: Handler, buf: BinaryIO) -> BytesIO:
        return Handler.run_ext((*self.exec_args(), *_GIFSICLE_ARGS), buf)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class _GifBase(ImageHandler):
    OUTPUT_FORMAT_STR = str(GifImageFile.format)
    SUFFIXES: tuple[str, ...] = (".gif",)
    PIPELINE: tuple[tuple[Tool, ...], ...] = (
        # gifsicle is preferred; PIL save acts as a fallback for the rare
        # case where the user disables gifsicle but still wants GIF handled.
        (GifsicleTool(),),
    )
    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType({"optimize": True})


class Gif(_GifBase):
    """Still GIF handler."""

    OUTPUT_FILE_FORMAT = FileFormat(
        _GifBase.OUTPUT_FORMAT_STR, lossless=True, animated=False
    )
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})


class GifAnimated(_GifBase):
    """Animated GIF handler."""

    OUTPUT_FILE_FORMAT = FileFormat(
        _GifBase.OUTPUT_FORMAT_STR, lossless=True, animated=True
    )
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})


# ---------------------------------------------------------------------------
# Plugin descriptor
# ---------------------------------------------------------------------------

PLUGIN = Plugin(
    name="GIF",
    handlers=(Gif, GifAnimated),
    routes=(
        Route(file_format=Gif.OUTPUT_FILE_FORMAT, native=Gif),
        Route(file_format=GifAnimated.OUTPUT_FILE_FORMAT, native=GifAnimated),
    ),
    default_enabled=True,
)
