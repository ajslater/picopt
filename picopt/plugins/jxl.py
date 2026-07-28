"""
JPEG XL format plugin.

Owns: JXL (still). Tool: the ``pillow-jxl-plugin`` Pillow codec, driven
in-process. Two handlers with different jobs:

* :class:`JxlLossless` re-encodes lossless JXL in place and is the target
  for every lossless still conversion. Only files that
  :func:`picopt.pillow.jxl.is_lossless` accepts are routed here, so lossy
  (XYB-encoded) JXL is left alone exactly as lossy WebP is.
* :class:`JxlFromJpeg` converts JPEG to JXL by lossless bitstream
  reconstruction, which is reversible: the original JPEG can be restored
  byte for byte. It is doubly opt-in — ``--convert-to JXL`` *and*
  ``--convert-jpeg-to-jxl`` — because picopt otherwise never uses a lossy
  format as a conversion source.

Animation is deliberately absent: the codec can neither read nor write
animated JXL, so no animated route points here in either direction.
"""

from __future__ import annotations

import os
from io import BytesIO
from tempfile import mkstemp
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from loguru import logger
from PIL import Image
from typing_extensions import override

from picopt.pillow.jxl import JXL_FORMAT_STR
from picopt.plugins.base import (
    Handler,
    ImageHandler,
    InternalTool,
    PILSaveTool,
    Plugin,
    Route,
    Tool,
)
from picopt.plugins.base.format import FileFormat
from picopt.plugins.gif import Gif
from picopt.plugins.jpeg import Jpeg
from picopt.plugins.png import Png
from picopt.plugins.webp.static import WebPLossless

if TYPE_CHECKING:
    from pathlib import Path
    from typing import BinaryIO

# effort 9 is the slowest setting that still targets size; 10 exists but
# costs disproportionately more time for a fraction of a percent.
_EFFORT: Final[int] = 9

# The modes pillow-jxl-plugin can encode. Anything else raises
# NotImplementedError, so it is converted first.
_VALID_MODES: Final[frozenset[str]] = frozenset({"RGB", "RGBA", "L", "LA", "I;16", "F"})
# Substitutes for the modes the encoder rejects. Palette images need the
# transparency check, so they are resolved in code rather than here.
_MODE_SUBSTITUTES: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        "1": "L",
        "I": "I;16",
        "PA": "RGBA",
        "CMYK": "RGB",
        "YCbCr": "RGB",
        "LAB": "RGB",
        "HSV": "RGB",
    }
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class JpegXlReconstructTool(InternalTool):
    """
    Transcode a JPEG into JXL, preserving the original JPEG bitstream.

    The codec only takes its reconstruction path when PIL knows the source
    *filename*, and PIL sets that only when opened from a path — never from
    a file object. So this tool opens by path, spilling to a temp file for
    inputs that have none (archive members). Without that, the encode
    silently falls back to a plain pixel encode: still lossless, but no
    longer reversible and usually larger.
    """

    name = "pil2jxl_jpeg"
    module_name = "pillow_jxl"
    PACKAGE_NAME = "pillow-jxl-plugin"

    _SAVE_KWARGS: Final[MappingProxyType[str, Any]] = MappingProxyType(
        {
            "lossless_jpeg": True,
            # Belt and braces: if the reconstruction path is ever skipped,
            # this keeps the pixel fallback lossless instead of quality 90.
            "lossless": True,
            "effort": _EFFORT,
        }
    )

    @override
    def run_stage(self, handler: Handler, buf: BinaryIO) -> BinaryIO:
        input_path, is_tmp = self._input_path(handler, buf)
        try:
            output_buffer = BytesIO()
            with Image.open(input_path) as image:
                image.save(output_buffer, JXL_FORMAT_STR, **self._SAVE_KWARGS)
        finally:
            if is_tmp:
                input_path.unlink(missing_ok=True)
        return output_buffer

    @staticmethod
    def _input_path(handler: Handler, buf: BinaryIO) -> tuple[Path, bool]:
        """Return a real path for the input and whether it is ours to delete."""
        path = handler.path_info.path
        if path is not None and not isinstance(buf, BytesIO):
            return path, False
        working_path = handler.get_working_path()
        fd, tmp_str = mkstemp(prefix=working_path.name + ".", suffix=".jpg")
        os.close(fd)
        tmp_path = type(working_path)(tmp_str)
        buf.seek(0)
        with tmp_path.open("wb") as tmp_file:
            tmp_file.write(buf.read())
        buf.seek(0)
        return tmp_path, True


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class JxlLossless(ImageHandler):
    """Lossless still JXL handler."""

    OUTPUT_FORMAT_STR = JXL_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(JXL_FORMAT_STR, lossless=True, animated=False)
    # OUTPUT_FILE_FORMAT is deliberately absent: pil_save short-circuits when
    # the input is already an acceptable input format, which for a
    # single-tier JXL -> JXL pipeline would make re-optimization a no-op.
    # Png is listed so this handler is probed whenever PNG is requested,
    # which is what makes `-f PNG -c JXL` work.
    INPUT_FILE_FORMATS = frozenset({Png.OUTPUT_FILE_FORMAT})
    SUFFIXES: tuple[str, ...] = (".jxl",)

    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {"lossless": True, "effort": _EFFORT}
    )
    PIPELINE: tuple[tuple[Tool, ...], ...] = (
        (PILSaveTool(target_format_str=JXL_FORMAT_STR, name="pil2jxl"),),
    )

    @override
    def prepare_info(self, format_str: str) -> MappingProxyType[str, Any]:
        """Suppress the encoder's own EXIF fallback when stripping metadata."""
        info = super().prepare_info(format_str)
        if format_str == JXL_FORMAT_STR and not self.config.keep_metadata:
            # Given no exif kwarg, the encoder reads EXIF off the opened
            # image itself, which would quietly defeat --strip-metadata.
            # An empty value takes the kwarg branch and writes no EXIF box.
            info = MappingProxyType({**info, "exif": b""})
        return info

    def _substitute_mode(self, image: Image.Image) -> str | None:
        """Return a mode the encoder accepts, or None if it accepts this one."""
        if image.mode in _VALID_MODES:
            return None
        if image.mode == "P":
            return "RGBA" if "transparency" in image.info else "RGB"
        return _MODE_SUBSTITUTES.get(image.mode, "RGB")

    @override
    def prepare_image(self, image: Image.Image, format_str: str) -> Image.Image:
        """Convert modes the JXL encoder cannot represent."""
        if format_str != JXL_FORMAT_STR:
            return image
        mode = self._substitute_mode(image)
        if mode is None:
            return image
        msg = (
            f"Converting {self.path_info.full_output_name()} from mode "
            f"{image.mode} to {mode} for JPEG XL"
        )
        logger.debug(msg)
        return image.convert(mode)


class JxlFromJpeg(ImageHandler):
    """Reversible JPEG to JXL transcoder, gated behind its own option."""

    OUTPUT_FORMAT_STR = JXL_FORMAT_STR
    OUTPUT_FILE_FORMAT = JxlLossless.OUTPUT_FILE_FORMAT
    INPUT_FILE_FORMATS = frozenset({Jpeg.OUTPUT_FILE_FORMAT})
    SUFFIXES: tuple[str, ...] = (".jxl",)
    CONFIG_ENABLED_KEY = "convert_jpeg_to_jxl"

    PIPELINE: tuple[tuple[Tool, ...], ...] = ((JpegXlReconstructTool(),),)


# ---------------------------------------------------------------------------
# Plugin descriptor
# ---------------------------------------------------------------------------

PLUGIN = Plugin(
    name="JXL",
    handlers=(JxlLossless, JxlFromJpeg),
    routes=(
        # Native, plus the reverse conversions out of JXL.
        Route(
            file_format=JxlLossless.OUTPUT_FILE_FORMAT,
            native=JxlLossless,
            convert=(WebPLossless, Png),
        ),
        # Lossless still sources. Formats owned by pil_convertible (BMP,
        # TIFF, PNM, …) get JXL added to their convert chain there.
        Route(file_format=Png.OUTPUT_FILE_FORMAT, convert=(JxlLossless,)),
        Route(file_format=Gif.OUTPUT_FILE_FORMAT, convert=(JxlLossless,)),
        Route(file_format=WebPLossless.OUTPUT_FILE_FORMAT, convert=(JxlLossless,)),
        # The one lossy source picopt will convert, and only on request.
        Route(file_format=Jpeg.OUTPUT_FILE_FORMAT, convert=(JxlFromJpeg,)),
    ),
    convert_targets=(JxlLossless, JxlFromJpeg),
    default_enabled=True,
)
