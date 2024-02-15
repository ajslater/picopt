#!/usr/bin/env python
"""Get raw jpeg xml from Pillow."""
# XXX This only seems to get some XMP data. xmp-tool finds more.
import struct

from PIL.JpegImagePlugin import JpegImageFile

APP1_SECTION_DELIMETER = b"\x00"
XAP_MARKER = b"http://ns.adobe.com/xap/1.0/"
SOI_MARKER = b"\xFF\xD8"
EOI_MARKER = b"\xFF\xE1"


def get_jpeg_xmp(image: JpegImageFile) -> str | None:
    """Get raw jpeg xml from Pillow."""
    xmp = None
    # Copied from PIL JpegImageFile
    for segment, content in image.applist:  # type: ignore
        if segment == "APP1":
            sections = content.split(APP1_SECTION_DELIMETER)
            marker, xmp_tags = sections[:2]
            if marker == XAP_MARKER:
                xmp = xmp_tags.decode()
                break
    return xmp


def set_jpeg_xmp(jpeg_data: bytes, xmp: str) -> bytes:
    """Insert xmp data into jpeg."""
    jpeg_buffer = bytearray(jpeg_data)
    soi_index = jpeg_buffer.find(SOI_MARKER)
    if soi_index == -1:
        reason = "SOI marker not found in JPEG buffer."
        raise ValueError(reason)
    xmp_bytes = (
        XAP_MARKER
        + APP1_SECTION_DELIMETER
        + xmp.encode("utf-8")
        + APP1_SECTION_DELIMETER
    )
    return (
        jpeg_buffer[: soi_index + len(SOI_MARKER)]
        + EOI_MARKER
        + struct.pack("<H", len(xmp_bytes) + len(EOI_MARKER))
        + xmp_bytes
        + jpeg_buffer[soi_index + len(SOI_MARKER) :]
    )


def main(fn: str):
    """Test function with fn."""
    from PIL import Image

    with Image.open(fn) as image:
        xmp = get_jpeg_xmp(image)  # type: ignore
    print(xmp)  # noqa: T201


if __name__ == "__main__":
    import sys

    main(sys.argv[1])
