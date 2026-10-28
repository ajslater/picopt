"""
JPEG format plugin.

Owns still JPEG: lossless recompression with mozjpeg. Multi-picture JPEGs
(MPO) belong to the MPO plugin.
"""

from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

from loguru import logger
from PIL.JpegImagePlugin import JpegImageFile
from typing_extensions import override

from picopt.pillow import jpeg_trailer, mpf
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
    """
    Lossless mozjpeg recompression.

    mozjpeg reads only the first image and drops whatever follows its EOI:
    the gain map of an Ultra HDR photo, the video of a Motion Photo. A JPEG
    keeps that data, unchanged, after its recompressed image. Stripping
    metadata drops it with the XMP and MP Index that point to it, and
    converting an MPO keeps only its first image.
    """

    name = "mozjpeg"
    module_name = "mozjpeg_lossless_optimization"

    @override
    def run_stage(self, handler: Handler, buf: BinaryIO) -> BytesIO:
        import mozjpeg_lossless_optimization
        from mozjpeg_lossless_optimization import COPY_MARKERS

        keep_metadata = handler.config.keep_metadata
        copy = COPY_MARKERS.ALL if keep_metadata else COPY_MARKERS.NONE
        data = buf.read()
        end = None
        if keep_metadata and handler.input_file_format == Jpeg.OUTPUT_FILE_FORMAT:
            end = jpeg_trailer.image_end(data)
        image = mozjpeg_lossless_optimization.optimize(data[:end], copy=copy)
        if end is None or end == len(data):
            return BytesIO(image)
        try:
            return BytesIO(jpeg_trailer.rejoin(data, end, image))
        except mpf.MpfError as exc:
            name = handler.path_info.full_output_name()
            logger.warning(f"{name}: {exc}; leaving it unchanged.")
            return BytesIO(data)


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
