"""
MPO format plugin.

An MPO is a multi-picture JPEG: a primary JPEG followed by more JPEGs, such as
camera thumbnails, an iPhone's HDR gain map, or the second view of a stereo
pair, all listed in an MP Index inside the primary. iPhones and many cameras
save MPOs with a ``.jpg`` or ``.jpeg`` suffix.

- ``-x MPO`` optimizes every image losslessly with mozjpeg and rewrites the
  index, so the file stays an MPO under its own name.
- ``-x MPO -c JPEG`` keeps only the primary image, as an ordinary JPEG.

This is its own plugin, off by default, because every handler in a
default-enabled plugin enables its format by default.
"""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from PIL.MpoImagePlugin import MpoImageFile
from typing_extensions import override

from picopt.exceptions import UnreadableImageError
from picopt.pillow import mpf
from picopt.plugins.base import ImageHandler, Plugin, Route
from picopt.plugins.base.format import FileFormat
from picopt.plugins.base.tool import StdLibTool
from picopt.plugins.jpeg import Jpeg, MozJpegTool

if TYPE_CHECKING:
    from typing import BinaryIO

    from picopt.plugins.base import Handler, Tool

MPO_FILE_FORMAT = FileFormat(str(MpoImageFile.format), lossless=False, animated=True)


def _parse(data: bytes) -> mpf.MpIndex:
    if (index := mpf.parse(data)) is None:
        msg = "no readable MP Index"
        raise mpf.MpfError(msg)
    return index


def _malformed(exc: mpf.MpfError) -> UnreadableImageError:
    return UnreadableImageError(f"malformed MPO ({exc})")


def _optimize(image: bytes) -> bytes:
    """Recompress one image losslessly, keeping it if that doesn't help."""
    import mozjpeg_lossless_optimization
    from mozjpeg_lossless_optimization import COPY_MARKERS

    # Always copy every marker: the MPF index and a gain map's own XMP are
    # structure, not removable metadata.
    optimized = mozjpeg_lossless_optimization.optimize(image, copy=COPY_MARKERS.ALL)
    return optimized if len(optimized) < len(image) else image


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class MozJpegMpoTool(MozJpegTool):
    """Recompress every image in an MPO and rewrite its MP Index."""

    @override
    def run_stage(self, handler: Handler, buf: BinaryIO) -> BytesIO:
        data = buf.read()
        try:
            index = _parse(data)
            images = mpf.split(data, index)
            primary, *others = images
            # An item listed in a GContainer has its byte length recorded
            # in the primary's XMP, so leave every appended image as it is.
            if not mpf.has_gcontainer(primary):
                others = [_optimize(image) for image in others]
            optimized = mpf.rebuild(data, index, (_optimize(primary), *others))
        except mpf.MpfError as exc:
            raise _malformed(exc) from exc
        return BytesIO(optimized)


class MpoExtractTool(StdLibTool):
    """Extract the primary image of an MPO as an ordinary JPEG."""

    name = "mpo_extract"
    module_name = "struct"

    @override
    def run_stage(self, handler: Handler, buf: BinaryIO) -> BytesIO:
        data = buf.read()
        try:
            # The primary already carries the file's EXIF, XMP and ICC
            # profile; only the index of the images left behind goes.
            jpeg = mpf.strip(mpf.primary(data, _parse(data)))
        except mpf.MpfError as exc:
            raise _malformed(exc) from exc
        return BytesIO(jpeg)


class OptionalMozJpegTool(MozJpegTool):
    """mozjpeg as an optional stage: skipped when it's missing or disabled."""

    required = False


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class Mpo(ImageHandler):
    """Optimize an MPO in place, keeping every image."""

    OUTPUT_FORMAT_STR = MPO_FILE_FORMAT.format_str
    OUTPUT_FILE_FORMAT = MPO_FILE_FORMAT
    INPUT_FILE_FORMATS = frozenset({MPO_FILE_FORMAT})
    # The JPEG suffixes are listed so an MPO saved as IMG.jpeg keeps its name.
    SUFFIXES: tuple[str, ...] = (".mpo", ".jpg", ".jpeg")
    PIPELINE: tuple[tuple[Tool, ...], ...] = ((MozJpegMpoTool(),),)


class JpegFromMpo(Jpeg):
    """
    Convert an MPO to a JPEG of its primary image.

    The file keeps its name, ``.mpo`` included: stereo cameras save
    ``DSCF0001.MPO`` beside ``DSCF0001.JPG``, which a rename would overwrite.
    """

    INPUT_FILE_FORMATS = frozenset({MPO_FILE_FORMAT})
    PIPELINE: tuple[tuple[Tool, ...], ...] = (
        (MpoExtractTool(),),
        (OptionalMozJpegTool(),),
    )


# ---------------------------------------------------------------------------
# Plugin descriptor
# ---------------------------------------------------------------------------

PLUGIN = Plugin(
    name="MPO",
    handlers=(Mpo, JpegFromMpo),
    routes=(Route(file_format=MPO_FILE_FORMAT, native=Mpo, convert=(JpegFromMpo,)),),
)
