"""
PNG format plugin.

Owns: PNG (still + animated). Tools: oxipng (internal Python), pngout
(external, optional). Inputs from convertible PIL formats are routed here
by the pil_convertible plugin.
"""

from __future__ import annotations

from io import BytesIO
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from PIL.PngImagePlugin import PngImageFile
from typing_extensions import override

from picopt.pillow.png_bit_depth import png_bit_depth
from picopt.plugins.base import (
    ExternalTool,
    Handler,
    ImageHandler,
    InternalTool,
    PILSaveTool,
    Plugin,
    Route,
    Tool,
)
from picopt.plugins.base.format import FileFormat
from picopt.plugins.gif import Gif, GifAnimated

if TYPE_CHECKING:
    from typing import BinaryIO

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

_OXIPNG_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
    {
        "level": 3,
        "fix_errors": True,
        "force": True,
        "optimize_alpha": True,
    }
)


class OxiPngTool(InternalTool):
    """Optimize a PNG buffer in-process via the oxipng Python binding."""

    name = "oxipng"
    module_name = "oxipng"
    PACKAGE_NAME = "pyoxipng"

    @override
    def run_stage(self, handler: Handler, buf: BinaryIO) -> BytesIO:
        import oxipng

        opts = dict(_OXIPNG_KWARGS)
        if handler.config.png_max:
            opts["level"] = 5
            opts["deflate"] = oxipng.Deflaters.zopfli(15)
        if not handler.config.keep_metadata:
            opts["strip"] = oxipng.StripChunks.safe()
        buf.seek(0)
        with buf:
            return BytesIO(oxipng.optimize_from_memory(buf.read(), **opts))


_PNGOUT_ARGS: tuple[str, ...] = ("-", "-", "-force", "-y", "-q")
_PNGOUT_DEPTH_MAX = 8


class PngOutTool(ExternalTool):
    """Optional external optimizer; only runs on <=8-bit PNGs."""

    name = "pngout"
    binary = "pngout"
    required = False
    version_args = ()

    @override
    def parse_version(self, version: str) -> str:
        version = super().parse_version(version)
        return " ".join(version.split()[-3:])

    @override
    def run_stage(self, handler: Handler, buf: BinaryIO) -> BinaryIO:
        try:
            depth = png_bit_depth(buf)
        except ValueError as exc:
            handler._printer.warn(str(exc))  # noqa: SLF001
            return buf
        if not depth or depth > _PNGOUT_DEPTH_MAX or depth < 1:
            handler._printer.skip(f"pngout for {depth} bit PNG", handler.path_info)  # noqa: SLF001
            return buf
        keep_arg = ("-k1",) if handler.config.keep_metadata else ("-k0",)
        return self.run_ext((*self.exec_args(), *_PNGOUT_ARGS, *keep_arg), buf)

    @staticmethod
    def run_ext(args: tuple[str, ...], buf: BinaryIO) -> BytesIO:
        """Run external program."""
        return Handler.run_ext(args, buf)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class _PngBase(ImageHandler):
    """
    Common PNG handler base.

    Subclasses just override OUTPUT_FILE_FORMAT for animated/still.
    """

    OUTPUT_FORMAT_STR = str(PngImageFile.format)
    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType({"optimize": True})


class Png(_PngBase):
    """Still PNG handler."""

    OUTPUT_FILE_FORMAT = FileFormat(
        _PngBase.OUTPUT_FORMAT_STR, lossless=True, animated=False
    )
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    SUFFIXES: tuple[str, ...] = (".png",)
    PIPELINE: tuple[tuple[Tool, ...], ...] = (
        (
            PILSaveTool(
                target_format_str="PNG",
                save_kwargs={"compress_level": 0},
                name="pil2png",
            ),
        ),
        (OxiPngTool(),),
        (PngOutTool(),),
    )


class PngAnimated(_PngBase):
    """
    Animated (APNG) handler.

    Note: still uses the still-PNG pipeline. APNG is identified at detection
    time and routed here; the pipeline is the same.
    """

    OUTPUT_FILE_FORMAT = FileFormat(
        _PngBase.OUTPUT_FORMAT_STR, lossless=True, animated=True
    )
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    SUFFIXES: tuple[str, ...] = (".png", ".apng")
    PIPELINE: tuple[tuple[Tool, ...], ...] = Png.PIPELINE


# ---------------------------------------------------------------------------
# Plugin descriptor
# ---------------------------------------------------------------------------

PLUGIN = Plugin(
    name="PNG",
    handlers=(Png, PngAnimated),
    routes=(
        Route(file_format=Png.OUTPUT_FILE_FORMAT, native=Png),
        Route(file_format=PngAnimated.OUTPUT_FILE_FORMAT, native=PngAnimated),
        Route(file_format=Gif.OUTPUT_FILE_FORMAT, convert=(Png,)),
        Route(file_format=GifAnimated.OUTPUT_FILE_FORMAT, convert=(PngAnimated,)),
    ),
    convert_targets=(Png, PngAnimated),
    default_enabled=True,
)
