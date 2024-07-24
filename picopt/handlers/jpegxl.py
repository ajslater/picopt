"""JPEG format."""

from io import BytesIO
from types import MappingProxyType
from typing import BinaryIO

import pillow_jxl  # noqa: F401, type: ignore
from PIL import Image
from pillow_jxl.JpegXLImagePlugin import JXLImageFile
from termcolor import cprint

from picopt.formats import FileFormat
from picopt.handlers.image import ImageHandler

MPO_METADATA: int = 45058
MPO_TYPE_PRIMARY: str = "Baseline MP Primary Image"


class JpegXL(ImageHandler):
    """JPEG XL format class."""

    OUTPUT_FORMAT_STR = str(JXLImageFile.format)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, False, False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS = (("pil2jpegxl",),)
    PIL2_KWARGS = MappingProxyType(
        {"lossless": False, "effort": 9, "format": OUTPUT_FORMAT_STR}
    )

    def pil2jpegxl(
        self,
        exec_args: tuple[str, ...],  # noqa: ARG002
        input_buffer: BinaryIO,
    ) -> BinaryIO:
        """Save with JpegXL."""
        jpegxl_data = BytesIO()
        try:
            with Image.open(input_buffer) as im:
                im.save(jpegxl_data, **self.PIL2_KWARGS)
        except Exception as exc:
            cprint(f"WARNING: could not save JPEG XL: {exc}", "yellow")

        self.input_file_format = self.OUTPUT_FILE_FORMAT
        return jpegxl_data


class JpegXLLossless(JpegXL):
    """JPEG XL format class."""

    OUTPUT_FILE_FORMAT = FileFormat(JpegXL.OUTPUT_FORMAT_STR, True, False)
    PIL2_KWARGS = MappingProxyType(
        {"lossless": True, "effort": 9, "format": JpegXL.OUTPUT_FORMAT_STR}
    )
