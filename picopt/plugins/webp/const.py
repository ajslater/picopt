"""Constants shared across the WebP plugin modules."""

from PIL.WebPImagePlugin import WebPImageFile

from picopt.plugins.base.format import FileFormat

WEBP_FORMAT_STR: str = str(WebPImageFile.format)

# cwebp >= 1.2.3 accepts PPM and TIFF input directly. Older releases need a
# pre-conversion. CWEBP_TOOL.probe() detects the version once and stores the
# result on the singleton; handlers that benefit widen their accepted input
# formats with these entries in __init__.
_PPM_FILE_FORMAT = FileFormat("PPM", lossless=True, animated=False)
_TIFF_FILE_FORMAT = FileFormat("TIFF", lossless=True, animated=False)
MODERN_CWEBP_FORMATS: frozenset[FileFormat] = frozenset(
    {_PPM_FILE_FORMAT, _TIFF_FILE_FORMAT}
)
