"""
JPEG format plugin.

Owns: JPEG (still), and the MPO → JPEG conversion route. The MPO format
constant lives here because nothing else in picopt knows about MPO; it's
exclusively a JPEG concern.
"""

from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

from PIL.JpegImagePlugin import JpegImageFile
from PIL.MpoImagePlugin import MpoImageFile
from typing_extensions import override

from picopt.formats import FileFormat
from picopt.pillow.jpeg_xmp import set_jpeg_xmp
from picopt.plugins.base import (
    Handler,
    ImageHandler,
    InternalTool,
    Plugin,
    Route,
    Tool,
)

# Public so the pil_convertible plugin can reference it.
MPO_FILE_FORMAT = FileFormat(str(MpoImageFile.format), lossless=False, animated=True)

_MPO_METADATA: int = 45058
_MPO_TYPE_PRIMARY: str = "Baseline MP Primary Image"


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


class MpoExtractTool(InternalTool):
    """
    Extract the primary image from an MPO and copy metadata.

    Acts as a fallback at the same pipeline tier as MozJpeg. mozjpeg handles
    plain JPEGs and MPOs (the first JPEG frame in an MPO is a complete JPEG)
    so in practice this tool is rarely the selected stage. It exists for
    cases where mozjpeg is unavailable or disabled.
    """

    name = "mpo_extract"
    module_name = "piexif"

    @override
    def run_stage(self, handler: Handler, buf: BinaryIO) -> BinaryIO:
        if handler.input_file_format != MPO_FILE_FORMAT:
            return buf
        if not isinstance(handler, Jpeg):
            return buf

        jpeg_data = self._extract_primary_frame(handler, buf)
        try:
            jpeg_data = self._copy_exif(handler, jpeg_data)
        except Exception as exc:
            handler._printer.warn(  # noqa: SLF001
                f"could not copy EXIF data for {handler.path_info.full_output_name()}",
                exc,
            )
        try:
            jpeg_data = self._copy_xmp(handler, jpeg_data)
        except Exception as exc:
            handler._printer.warn(  # noqa: SLF001
                f"could not copy XMP data for {handler.path_info.full_output_name()}",
                exc,
            )

        handler.input_file_format = handler.OUTPUT_FILE_FORMAT
        return BytesIO(jpeg_data)

    @staticmethod
    def _extract_primary_frame(handler: Jpeg, buf: BinaryIO) -> bytes:
        mpo_info = handler.info.pop("mpinfo", {})
        mpo_metadata_list = mpo_info.get(_MPO_METADATA, ())
        offset = size = -1
        for mpo_metadata in mpo_metadata_list:
            attr = mpo_metadata.get("Attribute", {})
            if attr.get("MPType") == _MPO_TYPE_PRIMARY:
                offset = mpo_metadata.get("DataOffset", -1)
                size = mpo_metadata.get("Size", -1)
                break
        if -1 in (offset, size):
            msg = f"{handler.original_path} could not find {_MPO_TYPE_PRIMARY} in MPO"
            raise ValueError(msg)
        buf.seek(offset)
        return buf.read(size)

    @staticmethod
    def _copy_exif(handler: Jpeg, jpeg_data: bytes) -> bytes:
        import piexif

        if exif := handler.info.get("exif"):
            output = BytesIO()
            piexif.insert(exif, jpeg_data, output)
            return output.read()
        return jpeg_data

    @staticmethod
    def _copy_xmp(handler: Jpeg, jpeg_data: bytes) -> bytes:
        if xmp := handler.info.get("xmp"):
            return set_jpeg_xmp(jpeg_data, xmp)
        return jpeg_data


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class Jpeg(ImageHandler):
    """JPEG handler."""

    OUTPUT_FORMAT_STR = str(JpegImageFile.format)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, lossless=False, animated=False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    SUFFIXES: tuple[str, ...] = (".jpg", ".jpeg", ".mpo")
    PIPELINE: tuple[tuple[Tool, ...], ...] = ((MozJpegTool(), MpoExtractTool()),)


# ---------------------------------------------------------------------------
# Plugin descriptor
# ---------------------------------------------------------------------------

PLUGIN = Plugin(
    name="JPEG",
    handlers=(Jpeg,),
    routes=(
        Route(file_format=Jpeg.OUTPUT_FILE_FORMAT, native=Jpeg),
        Route(file_format=MPO_FILE_FORMAT, convert=(Jpeg,)),
    ),
    convert_targets=(Jpeg,),
    default_enabled=True,
    extra_format_strs=frozenset({MPO_FILE_FORMAT.format_str}),
)
