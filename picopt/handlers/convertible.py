"""Convertible format definitions."""
# TODO move up out of handlers into file formats module
from PIL.BmpImagePlugin import BmpImageFile, DibImageFile
from PIL.CurImagePlugin import CurImageFile
from PIL.FitsImagePlugin import FitsImageFile
from PIL.FliImagePlugin import FliImageFile
from PIL.GifImagePlugin import GifImageFile
from PIL.ImageFile import ImageFile
from PIL.ImtImagePlugin import ImtImageFile
from PIL.PcxImagePlugin import PcxImageFile
from PIL.PixarImagePlugin import PixarImageFile
from PIL.PngImagePlugin import PngImageFile
from PIL.PpmImagePlugin import PpmImageFile
from PIL.PsdImagePlugin import PsdImageFile
from PIL.QoiImagePlugin import QoiImageFile
from PIL.SgiImagePlugin import SgiImageFile
from PIL.SpiderImagePlugin import SpiderImageFile
from PIL.SunImagePlugin import SunImageFile
from PIL.TgaImagePlugin import TgaImageFile
from PIL.TiffImagePlugin import TiffImageFile
from PIL.XbmImagePlugin import XbmImageFile
from PIL.XpmImagePlugin import XpmImageFile

from picopt.handlers.handler import FileFormat

# TIFF_LOSSY_COMPRESSION = frozenset({
#    "jpeg", "webp"
# })
# TODO move into factory
TIFF_LOSSLESS_COMPRESSION = frozenset(
    {
        None,
        "group3",
        "group4",
        "lzma",
        "packbits",
        "tiff_adobe_deflate",
        "tiff_ccitt",
        "tiff_lzw",
        "tiff_raw_16",
        "tiff_sgilog",
        "tiff_sgilog24",
        "tiff_thunderscan",
        "zstd",
    }
)
TIFF_FORMAT_STR = TiffImageFile.format
TIFF_FILE_FORMAT = FileFormat(TIFF_FORMAT_STR, True, False)
GIF_FORMAT_STR = GifImageFile.format
PNG_FORMAT_STR = PngImageFile.format
APNG_FILE_FORMAT = FileFormat(PNG_FORMAT_STR, True, True)
# TODO duplicates from handlers/svg.py
SVG_FORMAT_STR = "SVG"


def _create_file_format(
    image_file: type[ImageFile], animated: bool = False
) -> FileFormat:
    fmt: str = image_file.format  # type: ignore
    return FileFormat(fmt, True, animated)


# TODO should these be dicts?
# TODO fix CONVERTIBLE SPELLING
CONVERTABLE_FILE_FORMATS = frozenset(
    {
        _create_file_format(image_file)
        for image_file in (
            # PIL Read/Write lossless formats
            BmpImageFile,
            DibImageFile,
            PcxImageFile,
            PpmImageFile,
            # PngImageFile,
            SgiImageFile,
            SpiderImageFile,
            TgaImageFile,
            TiffImageFile,
            XbmImageFile,
            # GifImageFile,
            ##################################
            # PIL Read only lossless formats #
            ##################################
            CurImageFile,
            FitsImageFile,
            ImtImageFile,
            PixarImageFile,
            PsdImageFile,
            SunImageFile,
            XpmImageFile,
            QoiImageFile,
        )
    }
)
# TODO fix CONVERTIBLE SPELLING
CONVERTABLE_FORMAT_STRS = frozenset(
    {img_format.format_str for img_format in CONVERTABLE_FILE_FORMATS}
)
# TODO fix CONVERTIBLE SPELLING
CONVERTABLE_ANIMATED_FILE_FORMATS = frozenset(
    {
        _create_file_format(image_file, True)
        for image_file in (
            FliImageFile,
            # GifImageFile,
            # PngImageFile,
            TiffImageFile,
        )
    }
)
# TODO fix CONVERTIBLE SPELLING
CONVERTABLE_ANIMATED_FORMAT_STRS = frozenset(
    {img_format.format_str for img_format in CONVERTABLE_ANIMATED_FILE_FORMATS}
)

LOSSLESS_FORMAT_STRS = frozenset(
    CONVERTABLE_FORMAT_STRS
    | CONVERTABLE_ANIMATED_FORMAT_STRS
    | {GIF_FORMAT_STR, PNG_FORMAT_STR, SVG_FORMAT_STR}
)
