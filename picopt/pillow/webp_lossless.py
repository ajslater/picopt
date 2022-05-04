#!/usr/bin/env python3
"""
Determine if a webp is lossless.

This should be a part of Pillow
https://developers.google.com/speed/webp/docs/webp_lossless_bitstream_specification
"""
from pathlib import Path

from picopt.pillow.unpack import compare_header


RIFF_HEADER: tuple[bytes, ...] = (b"R", b"I", b"F", b"F")
WEBP_HEADER: tuple[bytes, ...] = (b"W", b"E", b"B", b"P")
VP8L_HEADER: tuple[bytes, ...] = (b"V", b"P", b"8", b"L")

COMPARATORS = ((0, RIFF_HEADER), (8, WEBP_HEADER), (12, VP8L_HEADER))


def is_lossless(filename: str) -> bool:
    """If a file is a png, get the bit depth from the standard position."""
    path = Path(filename)
    try:
        with path.open("rb") as img:
            for seek, byte_array in COMPARATORS:
                compare_header(img, seek, byte_array)
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
