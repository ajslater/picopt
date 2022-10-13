#!/usr/bin/env python3
"""
Determine if a webp is lossless.

This should be a part of Pillow
https://developers.google.com/speed/webp/docs/webp_lossless_bitstream_specification
"""
from dataclasses import dataclass
from pathlib import Path

from picopt.pillow.unpack import compare_header


@dataclass
class ImageHeader:
    """The seek location and value of a byte header."""

    offset: int
    bytes: tuple[bytes, ...]


RIFF_HEADER = ImageHeader(0, (b"R", b"I", b"F", b"F"))
WEBP_HEADER = ImageHeader(8, (b"W", b"E", b"B", b"P"))
VP8L_HEADER = ImageHeader(12, (b"V", b"P", b"8", b"L"))

HEADERS = (RIFF_HEADER, WEBP_HEADER, VP8L_HEADER)


def is_lossless(filename: str) -> bool:
    """Compare header types against lossless types."""
    path = Path(filename)
    try:
        with path.open("rb") as img:
            for header in HEADERS:
                compare_header(img, header.offset, header.bytes)
        return True
    except ValueError:
        return False


def main() -> None:
    """Stand alone cli tool for getting lossless status."""
    import sys

    lossless = is_lossless(sys.argv[1])
    print(lossless)


if __name__ == "__main__":
    main()
