#!/usr/bin/env python3
"""
Determine if a webp is lossless.

This should really be a part of Pillow
https://developers.google.com/speed/webp/docs/webp_lossless_bitstream_specification
"""
from pathlib import Path

from picopt.pillow.unpack import unpack


RIFF_HEADER = (b"R", b"I", b"F", b"F")
WEBP_HEADER = (b"W", b"E", b"B", b"P")
VP8L_HEADER = (b"V", b"P", b"8", b"L")


def is_lossless(filename: str) -> bool:
    """If a file is a png, get the bit depth from the standard position."""
    path = Path(filename)
    with path.open("rb") as img:
        img.seek(0)
        header = unpack("c", 4, img)
        if header != RIFF_HEADER:
            print(path, "is not a webp!")
            return False

        # skip past the block length header
        img.seek(8)

        webp = unpack("c", 4, img)
        if webp != WEBP_HEADER:
            print(path, "is not a webp!")
            return False

        vp8l = unpack("c", 4, img)
        return bool(vp8l == VP8L_HEADER)


def main() -> None:
    """Stand alone cli tool for getting lossless status."""
    import sys

    lossless = is_lossless(sys.argv[1])
    print(lossless)


if __name__ == "__main__":
    main()
