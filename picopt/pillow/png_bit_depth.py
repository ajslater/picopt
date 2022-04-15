#!/usr/bin/env python3
"""
Get the bit depth of a png image manually.

https://www.w3.org/TR/PNG-Chunks.html
This should be a part of Pillow
"""
from pathlib import Path
from typing import Optional

from termcolor import cprint

from picopt.pillow.unpack import compare_header, unpack


PNG_HEADER = (b"\x89", b"P", b"N", b"G", b"\r", b"\n", b"\x1a", b"\n")


def png_bit_depth(path: Path) -> Optional[int]:
    """If a file is a png, get the bit depth from the standard position."""
    try:
        with path.open("rb") as img:
            compare_header(img, 0, PNG_HEADER)

            img.seek(24)  # bit depth offset
            depth = unpack("b", 1, img)[0]
        return int(depth)
    except ValueError:
        cprint(f"WARNING: {path} is not a png!", "yellow")
        return None


def main() -> None:
    """Stand alone cli tool for getting png bit depth."""
    import sys

    bit_depth = png_bit_depth(Path(sys.argv[1]))
    print(bit_depth)


if __name__ == "__main__":
    main()
