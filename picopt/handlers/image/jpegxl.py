"""JPEG format."""

from io import BytesIO
from types import MappingProxyType
from typing import BinaryIO

import pillow_jxl  # noqa: F401, # pyright: ignore[reportUnusedImport]
from PIL import Image
from pillow_jxl import JpegXLImagePlugin
from pillow_jxl.JpegXLImagePlugin import JXLImageFile
from termcolor import cprint

from picopt.formats import FileFormat
from picopt.handlers.image import ImageHandler

MPO_METADATA: int = 45058
MPO_TYPE_PRIMARY: str = "Baseline MP Primary Image"


class JpegXL(ImageHandler):
    """JPEG XL format class."""

    OUTPUT_FORMAT_STR = str(JXLImageFile.format)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, lossless=False, animated=False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS = (("pil2jpegxl",),)
    PIL2_KWARGS = MappingProxyType({"effort": 9, "format": OUTPUT_FORMAT_STR})

    def pil2jpegxl(
        self,
        exec_args: tuple[str, ...],  # noqa: ARG002
        input_buffer: BinaryIO,
    ) -> BinaryIO:
        """Save with JpegXL."""
        jpegxl_data = BytesIO()
        try:
            with Image.open(input_buffer) as im:
                # HACK for unsupported modes
                # https://github.com/Isotr0py/pillow-jpegxl-plugin/blob/main/pillow_jxl/JpegXLImagePlugin.py#L139
                # if _save() NotImplementedError still exists.
                if im.mode not in JpegXLImagePlugin._VALID_JXL_MODES:  # noqa: SLF001
                    if self.config.verbose > 1:
                        cprint(
                            f"WARNING: Converting JPEGXL color mode from to {im.mode} RGB"
                        )
                    cim = im.convert("RGB")
                else:
                    cim = im
                args = {**self.PIL2_KWARGS}
                if not self.config.keep_metadata:
                    cim.info = {}
                    args["exif"] = {}
                with cim:
                    cim.save(jpegxl_data, **args)
        except Exception as exc:
            cprint(f"WARNING: could not save JPEG XL: {exc}", "yellow")

        self.input_file_format = self.OUTPUT_FILE_FORMAT
        return jpegxl_data


class JpegXLLossless(JpegXL):
    """JPEG XL Lossless format class."""

    OUTPUT_FILE_FORMAT = FileFormat(
        JpegXL.OUTPUT_FORMAT_STR, lossless=True, animated=False
    )
    PIL2_KWARGS = MappingProxyType({**JpegXL.PIL2_KWARGS, "lossless": True})
