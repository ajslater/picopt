"""Convertible format definitions."""
from dataclasses import dataclass

from PIL.BmpImagePlugin import BmpImageFile, DibImageFile
from PIL.CurImagePlugin import CurImageFile
from PIL.FitsImagePlugin import FitsImageFile
from PIL.FliImagePlugin import FliImageFile
from PIL.GifImagePlugin import GifImageFile
from PIL.ImtImagePlugin import ImtImageFile
from PIL.MpoImagePlugin import MpoImageFile
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


@dataclass(eq=True, frozen=True)
class FileFormat:
    """A file format, with image attributes."""

    format_str: str
    lossless: bool = True
    animated: bool = False


MPO_FILE_FORMAT = FileFormat(MpoImageFile.format, False, True)
SVG_FORMAT_STR = "SVG"
TIFF_FILE_FORMAT = FileFormat(TiffImageFile.format, True, False)
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
# TIFF_LOSSY_COMPRESSION = frozenset({
#    "jpeg", "webp"
# })
PNGINFO_XMP_KEY = "XML:com.adobe.xmp"
PPM_FILE_FORMAT = FileFormat(PpmImageFile.format, True, False)
MODERN_CWEBP_FORMATS = frozenset({PPM_FILE_FORMAT, TIFF_FILE_FORMAT})
MODERN_CWEBP_FORMAT_STRS = frozenset(
    sorted(fmt.format_str for fmt in MODERN_CWEBP_FORMATS)
)


_CONVERTABLE_PIL_IMAGE_FILES = (
    ###################################
    # PIL Read/Write lossless formats #
    ###################################
    BmpImageFile,
    DibImageFile,
    # GifImageFile,
    PcxImageFile,
    PpmImageFile,
    # PngImageFile,
    SgiImageFile,
    SpiderImageFile,
    TgaImageFile,
    TiffImageFile,
    XbmImageFile,
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
    ###################
    # Animated to not #
    ###################
    MpoImageFile,
)
CONVERTIBLE_FORMAT_STRS = frozenset(
    {img_file.format for img_file in _CONVERTABLE_PIL_IMAGE_FILES}
)

CONVERTIBLE_FILE_FORMATS = frozenset(
    {FileFormat(format_str, True, False) for format_str in CONVERTIBLE_FORMAT_STRS}
)
_CONVERTABLE_PIL_ANIMATED_IMAGE_FILES = (
    #################################
    # PIL lossless animated formats #
    #################################
    FliImageFile,
    # GifImageFile,
    # PngImageFile,
    TiffImageFile,
)
CONVERTIBLE_ANIMATED_FORMAT_STRS = frozenset(
    {img_file.format for img_file in _CONVERTABLE_PIL_ANIMATED_IMAGE_FILES}
)
CONVERTIBLE_ANIMATED_FILE_FORMATS = frozenset(
    {
        FileFormat(format_str, True, True)
        for format_str in CONVERTIBLE_ANIMATED_FORMAT_STRS
    }
)

LOSSLESS_FORMAT_STRS = frozenset(
    CONVERTIBLE_FORMAT_STRS - {MpoImageFile.format}
    | CONVERTIBLE_ANIMATED_FORMAT_STRS
    | {GifImageFile.format, PngImageFile.format, SVG_FORMAT_STR}
)
