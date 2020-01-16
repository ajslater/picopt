#!/usr/bin/env python3
"""
Get the bit depth of a png image manually.

This should really be a part of Pillow
"""
import struct

from pathlib import Path
from typing import BinaryIO
from typing import Optional
from typing import Tuple
from typing import Union


PNG_HEADER = (b"\x89", b"P", b"N", b"G", b"\r", b"\n", b"\x1a", b"\n")


def unpack(
    fmt_type: str, length: int, file_desc: BinaryIO
) -> Union[Tuple[bytes, ...], Tuple[int]]:
    """Unpack unformation from a file according to format string & length."""
    return struct.unpack(fmt_type * length, file_desc.read(length))


def png_bit_depth(path: Path) -> Optional[int]:
    """If a file is a png, get the bit depth from the standard position."""
    with open(path, "rb") as img:
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

    bit_depth = png_bit_depth(Path(sys.argv[1]))
    print(bit_depth)


if __name__ == "__main__":
    main()
