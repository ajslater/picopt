"""
JPEG format plugin.

Owns still JPEG: lossless recompression with mozjpeg. Multi-picture JPEGs
(MPO) belong to the MPO plugin.
"""

from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

from PIL.JpegImagePlugin import JpegImageFile
from typing_extensions import override

from picopt.plugins.base import (
    Handler,
    ImageHandler,
    InternalTool,
    Plugin,
    Route,
    Tool,
)
from picopt.plugins.base.format import FileFormat

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class MozJpegTool(InternalTool):
    """Lossless mozjpeg recompression."""

    name = "mozjpeg"
    module_name = "mozjpeg_lossless_optimization"

    @override
    def run_stage(self, handler: Handler, buf: BinaryIO) -> BytesIO:
        import mozjpeg_lossless_optimization
        from mozjpeg_lossless_optimization import COPY_MARKERS

        copy = COPY_MARKERS.ALL if handler.config.keep_metadata else COPY_MARKERS.NONE
        return BytesIO(mozjpeg_lossless_optimization.optimize(buf.read(), copy=copy))


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class Jpeg(ImageHandler):
    """JPEG handler."""

    OUTPUT_FORMAT_STR = str(JpegImageFile.format)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, lossless=False, animated=False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    SUFFIXES: tuple[str, ...] = (".jpg", ".jpeg", ".mpo")
    PIPELINE: tuple[tuple[Tool, ...], ...] = ((MozJpegTool(),),)


# ---------------------------------------------------------------------------
# Plugin descriptor
# ---------------------------------------------------------------------------

PLUGIN = Plugin(
    name="JPEG",
    handlers=(Jpeg,),
    routes=(Route(file_format=Jpeg.OUTPUT_FILE_FORMAT, native=Jpeg),),
    convert_targets=(Jpeg,),
    default_enabled=True,
)
