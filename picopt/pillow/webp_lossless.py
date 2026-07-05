#!/usr/bin/env python3
"""
Determine if a webp is lossless.

Parses the RIFF chunk structure rather than searching for byte strings, so
metadata payloads (ICC, EXIF, XMP) can neither hide the image chunk nor
fake one:
https://developers.google.com/speed/webp/docs/riff_container

This should be a part of Pillow.
"""

from pathlib import Path
from struct import unpack
from typing import BinaryIO

_RIFF_HEADER_LEN = 12
_CHUNK_HEADER_LEN = 8
# ANMF chunk: 16 bytes of frame parameters, then the frame's image chunks.
_ANMF_FRAME_PARAMS_LEN = 16
_LOSSLESS_FOURCC = b"VP8L"
_LOSSY_FOURCC = b"VP8 "
_ANIM_FRAME_FOURCC = b"ANMF"


def is_lossless(input_buffer: BinaryIO) -> bool:
    """
    Walk RIFF chunks until the first image data chunk decides losslessness.

    Leaves the buffer position at 0; the caller owns closing it.
    """
    input_buffer.seek(0)
    header = input_buffer.read(_RIFF_HEADER_LEN)
    if (
        len(header) < _RIFF_HEADER_LEN
        or header[:4] != b"RIFF"
        or header[8:12] != b"WEBP"
    ):
        return False
    try:
        while True:
            chunk_header = input_buffer.read(_CHUNK_HEADER_LEN)
            if len(chunk_header) < _CHUNK_HEADER_LEN:
                return False
            fourcc = chunk_header[:4]
            (size,) = unpack("<I", chunk_header[4:])
            if fourcc == _LOSSLESS_FOURCC:
                return True
            if fourcc == _LOSSY_FOURCC:
                return False
            if fourcc == _ANIM_FRAME_FOURCC:
                # Descend into the frame; image chunks follow the params.
                input_buffer.seek(_ANMF_FRAME_PARAMS_LEN, 1)
                continue
            # Chunk payloads are padded to even sizes.
            input_buffer.seek(size + (size & 1), 1)
    finally:
        input_buffer.seek(0)


def main() -> None:
    """Stand alone cli tool for getting lossless status."""
    import sys

    with Path(sys.argv[1]).open("rb") as f:
        lossless = is_lossless(f)
    print(lossless)  # noqa: T201


if __name__ == "__main__":
    main()
