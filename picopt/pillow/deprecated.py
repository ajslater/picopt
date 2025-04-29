"""Deprecated Pillow auxiliary functions."""

# Not sure I should delete these yet.
from collections.abc import Mapping
from contextlib import suppress
from io import BytesIO

from PIL import ImageCms
from PIL.JpegImagePlugin import JpegImageFile
from termcolor import cprint

_APP1_SECTION_DELIMETER = b"\x00"
_XAP_MARKER = b"http://ns.adobe.com/xap/1.0/"


def _get_xmp(info, image, path_name):
    """Get xmp data if not automatically included in info."""
    try:
        if "xmp" not in info:
            with suppress(AttributeError):
                if xmp := image.getxmp():
                    info["xmp"] = xmp
    except Exception as exc:
        cprint(
            f"WARNING: Failed to extract xmp data for {path_name} {exc}",
            "yellow",
        )


def _get_exif_bytes(info, image, path_name):
    """Get exif in bytes format for possible webp in the future."""
    try:
        with suppress(AttributeError):
            if exif := image.getexif():
                info["exif_bytes"] = exif.tobytes()
    except Exception as exc:
        cprint(
            f"WARNING: Failed to extract exif bytes data for {path_name} {exc}",
            "yellow",
        )


def extract_info_for_webp(keep_metadata, info, image, path_info):
    """Extract info manually for webp later in handler."""
    if not keep_metadata:
        return
    full_name = path_info.full_output_name()
    _get_xmp(info, image, full_name)
    _get_exif_bytes(info, image, full_name)


def _xmp_to_bytes(xmp_dict):
    """Convert xmp from dict to bytes for webp."""
    # Create an XMP metadata object
    xmp_meta = ImageCms.XMPMeta()
    xmp_meta.from_dict(xmp_dict)

    # Serialize the XMP metadata to a byte stream
    xmp_bytes = BytesIO()
    xmp_meta.to_bytes(xmp_bytes)
    return xmp_bytes.getvalue()


def webp_convert_info_metadata(config, info):
    """Convert info values into webp bytes."""
    if not config.keep_metadata:
        return
    if (xmp := info.get("xmp")) and isinstance(xmp, Mapping):
        info["xmp"] = _xmp_to_bytes(xmp)
    if (exif := info.get("exif")) and not isinstance(exif, bytes):
        info["exif"] = info.pop("exif_bytes", b"")
    if (icc_profile := info.get("icc_profile")) and not isinstance(icc_profile, bytes):
        info["icc_profile"] = icc_profile.encode()


def get_jpeg_xmp(image: JpegImageFile) -> str | None:
    """Get raw jpeg xml from Pillow."""
    # This only seems to get some XMP data. xmp-tool finds more.
    xmp = None
    # Copied from PIL JpegImageFile
    for segment, content in image.applist:
        if segment == "APP1":
            sections = content.split(_APP1_SECTION_DELIMETER)
            marker, xmp_tags = sections[:2]
            if marker == _XAP_MARKER:
                xmp = xmp_tags.decode()
                break
    return xmp
