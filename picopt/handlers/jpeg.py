"""JPEG format."""
from io import BytesIO
from typing import BinaryIO

import piexif
from PIL.JpegImagePlugin import JpegImageFile
from termcolor import cprint

from picopt.formats import MPO_FILE_FORMAT, FileFormat
from picopt.handlers.image import ImageHandler
from picopt.pillow.jpeg_xmp import set_jpeg_xmp

MPO_METADATA: int = 45058
MPO_TYPE_PRIMARY: str = "Baseline MP Primary Image"


class Jpeg(ImageHandler):
    """JPEG format class."""

    OUTPUT_FORMAT_STR = JpegImageFile.format
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, False, False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS = (("mozjpeg", "jpegtran", "pil2jpeg"),)
    _JPEGTRAN_ARGS_PREFIX = ("-optimize", "-progressive")
    # PIL Cannot save jpegs losslessly

    @classmethod
    def get_default_suffix(cls) -> str:
        """Override default suffix for jpeg."""
        return ".jpg"

    @classmethod
    def get_suffixes(cls, default_suffix: str) -> frozenset:
        """Initialize suffix instance variables."""
        return frozenset((default_suffix, "." + cls.OUTPUT_FORMAT_STR.lower()))

    def _jpegtran(self, exec_args: tuple[str, ...], input_buffer: BinaryIO) -> BytesIO:
        """Run the jpegtran type program."""
        copy_arg = "all" if self.config.keep_metadata else "none"
        args = (*exec_args, *self._JPEGTRAN_ARGS_PREFIX, "-copy", copy_arg)
        return self.run_ext(args, input_buffer)

    def mozjpeg(self, exec_args: tuple[str, ...], input_buffer: BinaryIO) -> BytesIO:
        """Create argument list for mozjpeg."""
        return self._jpegtran(exec_args, input_buffer)

    def jpegtran(self, exec_args: tuple[str, ...], input_buffer: BinaryIO) -> BytesIO:
        """Create argument list for jpegtran."""
        return self._jpegtran(exec_args, input_buffer)

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
        # XXX Much work because PIL doesn't have direct unprocessed file bytes access.
        if self.input_file_format != MPO_FILE_FORMAT:
            return input_buffer

        jpeg_data = self._mpo2jpeg_get_frame(input_buffer)
        try:
            jpeg_data = self._mpo2jpeg_copy_exif(jpeg_data)
        except Exception as exc:
            cprint(
                f"WARNING: could not copy EXIF data for {self.path_info.full_name()}: {exc}"
            )
        try:
            jpeg_data = self._mpo2jpeg_copy_xmp(jpeg_data)
        except Exception as exc:
            cprint(
                f"WARNING: could not copy XMP data for {self.path_info.full_name()}: {exc}"
            )

        self.input_file_format = self.OUTPUT_FILE_FORMAT
        return BytesIO(jpeg_data)
