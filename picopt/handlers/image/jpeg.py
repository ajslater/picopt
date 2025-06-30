"""JPEG format."""

from io import BytesIO
from typing import BinaryIO

import mozjpeg_lossless_optimization
import piexif
from mozjpeg_lossless_optimization import COPY_MARKERS
from PIL.JpegImagePlugin import JpegImageFile

from picopt.formats import MPO_FILE_FORMAT, FileFormat
from picopt.handlers.image import ImageHandler
from picopt.pillow.jpeg_xmp import set_jpeg_xmp

MPO_METADATA: int = 45058
MPO_TYPE_PRIMARY: str = "Baseline MP Primary Image"


class Jpeg(ImageHandler):
    """JPEG format class."""

    OUTPUT_FORMAT_STR = str(JpegImageFile.format)
    SUFFIXES: tuple[str, ...] = (".jpg", ".jpeg", ".mpo")
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, lossless=False, animated=False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS: tuple[tuple[str, ...], ...] = (("internal_mozjpeg", "pil2jpeg"),)
    # PIL Cannot save jpegs losslessly

    def internal_mozjpeg(
        self, _exec_args: tuple[str, ...], input_buffer: BinaryIO
    ) -> BytesIO:
        """Use mozjpeg-lossless-optimization."""
        copy = COPY_MARKERS.ALL if self.config.keep_metadata else COPY_MARKERS.NONE
        optimized = mozjpeg_lossless_optimization.optimize(
            input_buffer.read(), copy=copy
        )
        return BytesIO(optimized)

    def _mpo2jpeg_get_frame(self, input_buffer: BinaryIO) -> bytes:
        """Get Primary JPEG Offsets."""
        mpo_info = self.info.pop("mpinfo", {})
        mpo_metadata_list = mpo_info.get(MPO_METADATA, ())

        for mpo_metadata in mpo_metadata_list:
            attr = mpo_metadata.get("Attribute", {})
            mp_type = attr.get("MPType")
            if mp_type == MPO_TYPE_PRIMARY:
                offset = mpo_metadata.get("DataOffset", -1)
                size = mpo_metadata.get("Size", -1)
                break
        else:
            offset = size = -1

        if -1 in (offset, size):
            reason = f"{self.original_path} could not find {MPO_TYPE_PRIMARY} in MPO"
            raise ValueError(reason)
        input_buffer.seek(offset)
        return input_buffer.read(size)

    def _mpo2jpeg_copy_exif(self, jpeg_data: bytes) -> bytes:
        """Copy MPO EXIF into JPEG."""
        output_buffer = BytesIO()
        if exif := self.info.get("exif"):
            piexif.insert(exif, jpeg_data, output_buffer)
            return output_buffer.read()
        return jpeg_data

    def _mpo2jpeg_copy_xmp(self, jpeg_data: bytes) -> bytes:
        """Copy MPO XMP into JPEG manually."""
        if xmp := self.info.get("xmp"):
            jpeg_data = set_jpeg_xmp(jpeg_data, xmp)
        return jpeg_data

    def pil2jpeg(
        self,
        exec_args: tuple[str, ...],  # noqa: ARG002
        input_buffer: BinaryIO,
    ) -> BinaryIO:
        """Convert MPOs with primary images to jpeg."""
        # Much work because PIL doesn't have direct unprocessed file bytes access.
        if self.input_file_format != MPO_FILE_FORMAT:
            return input_buffer

        jpeg_data = self._mpo2jpeg_get_frame(input_buffer)
        try:
            jpeg_data = self._mpo2jpeg_copy_exif(jpeg_data)
        except Exception as exc:
            self._printer.warn(
                f"could not copy EXIF data for {self.path_info.full_output_name()}", exc
            )
        try:
            jpeg_data = self._mpo2jpeg_copy_xmp(jpeg_data)
        except Exception as exc:
            self._printer.warn(
                f"could not copy XMP data for {self.path_info.full_output_name()}", exc
            )

        self.input_file_format = self.OUTPUT_FILE_FORMAT
        return BytesIO(jpeg_data)
