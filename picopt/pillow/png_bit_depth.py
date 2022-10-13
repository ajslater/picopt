#!/usr/bin/env python3
"""
Get the bit depth of a png image manually.

https://www.w3.org/TR/PNG-Chunks.html
This should be a part of Pillow
"""
from pathlib import Path
from typing import Optional

from termcolor import cprint

from picopt.pillow.header import ImageHeader, unpack


PNG_HEADER = ImageHeader(0, (b"\x89", b"P", b"N", b"G", b"\r", b"\n", b"\x1a", b"\n"))
BIT_DEPTH_OFFSET = 24


def png_bit_depth(path: Path) -> Optional[int]:
    """If a file is a png, get the bit depth from the standard position."""
    result = None
    with path.open("rb") as img:
        if PNG_HEADER.compare(img):

            img.seek(BIT_DEPTH_OFFSET)  # bit depth offset
            depth = unpack("b", 1, img)[0]
            result = int(depth)
        else:
            cprint(f"WARNING: {path} is not a png!", "yellow")
    return result


def main() -> None:
    """Stand alone cli tool for getting png bit depth."""
    import sys

    bit_depth = png_bit_depth(Path(sys.argv[1]))
    print(bit_depth)


if __name__ == "__main__":
    main()
