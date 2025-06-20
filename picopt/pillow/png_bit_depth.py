#!/usr/bin/env python3
"""
Get the bit depth of a png image manually.

https://www.w3.org/TR/PNG-Chunks.html
This should be a part of Pillow
"""

from pathlib import Path
from typing import BinaryIO

from picopt.pillow.header import ImageHeader

_PNG_HEADER = ImageHeader(0, b"\x89PNG\r\n\x1a\n")
_BIT_DEPTH_OFFSET = 24


def png_bit_depth(buffer: BinaryIO) -> int | None:
    """If a file is a png, get the bit depth from the standard position."""
    if _PNG_HEADER.compare(buffer):
        buffer.seek(_BIT_DEPTH_OFFSET)  # bit depth offset
        depth = buffer.read(1)
        result = int.from_bytes(depth, byteorder="little")
    else:
        reason = "cannot find bit depth of non png"
        raise ValueError(reason)
    return result


def main() -> None:
    """Stand alone cli tool for getting png bit depth."""
    import sys  # noqa: PLC0415

    with Path(sys.argv[1]).open("rb") as f:
        bit_depth = png_bit_depth(f)
    print(bit_depth)  # noqa: T201


if __name__ == "__main__":
    main()
