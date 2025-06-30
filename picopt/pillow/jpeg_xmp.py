#!/usr/bin/env python
"""Get raw jpeg xml from Pillow."""

import struct

_APP1_SECTION_DELIMETER = b"\x00"
_XAP_MARKER = b"http://ns.adobe.com/xap/1.0/"
_SOI_MARKER = b"\xff\xd8"
_EOI_MARKER = b"\xff\xe1"


def set_jpeg_xmp(jpeg_data: bytes, xmp: str) -> bytes:
    """Insert xmp data into jpeg."""
    jpeg_buffer = bytearray(jpeg_data)
    soi_index = jpeg_buffer.find(_SOI_MARKER)
    if soi_index == -1:
        reason = "SOI marker not found in JPEG buffer."
        raise ValueError(reason)
    xmp_bytes = (
        _XAP_MARKER
        + _APP1_SECTION_DELIMETER
        + xmp.encode("utf-8")
        + _APP1_SECTION_DELIMETER
    )
    return (
        bytes(jpeg_buffer[: soi_index + len(_SOI_MARKER)])
        + _EOI_MARKER
        + struct.pack("<H", len(xmp_bytes) + len(_EOI_MARKER))
        + xmp_bytes
        + bytes(jpeg_buffer[soi_index + len(_SOI_MARKER) :])
    )
