#!/usr/bin/env python3
"""
Determine if a webp is lossless.

This should be a part of Pillow
https://developers.google.com/speed/webp/docs/webp_lossless_bitstream_specification
"""

from io import BufferedReader, BytesIO
from mmap import ACCESS_READ, mmap
from pathlib import Path

from picopt.pillow.header import ImageHeader

# RIFF_HEADER = ImageHeader(0, b"RIFF"))
# WEBP_HEADER = ImageHeader(8, b"WEBP"))
_VP8_HEADER = ImageHeader(12, b"VP8")
_VP8L_HEADER = b"VP8L"
_SEARCH_LEN = 128


def is_lossless(input_buffer: BytesIO | BufferedReader) -> bool:
    """Compare header types against lossless types."""
    result = True

    buffer: BytesIO | mmap = (
        mmap(input_buffer.fileno(), 0, access=ACCESS_READ)
        if isinstance(input_buffer, BufferedReader)
        else input_buffer
    )

    if not _VP8_HEADER.compare(buffer):
        result = False
    else:
        x = buffer.read(1)
        if x == b"L":
            result = True
        elif x == b"X":
            finder = (
                buffer
                if isinstance(buffer, mmap)
                else bytearray(buffer.read(_SEARCH_LEN))
            )
            result = finder.find(_VP8L_HEADER) != -1
        else:
            result = False

    input_buffer.close()
    buffer.close()
    return result


def main() -> None:
    """Stand alone cli tool for getting lossless status."""
    import sys

    with Path(sys.argv[1]).open("rb") as f:
        lossless = is_lossless(f)
    print(lossless)  # noqa: T201


if __name__ == "__main__":
    main()
