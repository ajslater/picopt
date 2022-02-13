#!/usr/bin/env python3
"""
Get the bit depth of a png image manually.

This should really be a part of Pillow
"""
from pathlib import Path
from typing import Optional

from picopt.pillow.unpack import unpack


PNG_HEADER = (b"\x89", b"P", b"N", b"G", b"\r", b"\n", b"\x1a", b"\n")


def png_bit_depth(filename: str) -> Optional[int]:
    """If a file is a png, get the bit depth from the standard position."""
    path = Path(filename)
    with path.open("rb") as img:
        img.seek(0)
        header = unpack("c", 8, img)
        if header != PNG_HEADER:
            print(path, "is not a png!")
            return None

        img.seek(24)  # bit depth offset
        depth = unpack("b", 1, img)[0]
        return int(depth)


def main() -> None:
    """Stand alone cli tool for getting png bit depth."""
    import sys

    bit_depth = png_bit_depth(sys.argv[1])
    print(bit_depth)


if __name__ == "__main__":
    main()
