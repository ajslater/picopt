#!/usr/bin/env python
"""Get raw jpeg xml from Pillow."""

import struct

APP1_SECTION_DELIMETER = b"\x00"
XAP_MARKER = b"http://ns.adobe.com/xap/1.0/"
SOI_MARKER = b"\xff\xd8"
EOI_MARKER = b"\xff\xe1"


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
        bytes(jpeg_buffer[: soi_index + len(SOI_MARKER)])
        + EOI_MARKER
        + struct.pack("<H", len(xmp_bytes) + len(EOI_MARKER))
        + xmp_bytes
        + bytes(jpeg_buffer[soi_index + len(SOI_MARKER) :])
    )
