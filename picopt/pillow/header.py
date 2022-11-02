"""Unpack items from a file descriptor."""
import struct

from dataclasses import dataclass
from typing import BinaryIO, Union


def unpack(
    fmt_type: str, length: int, file_desc: BinaryIO
) -> Union[tuple[bytes, ...], tuple[int]]:
    """Unpack information from a file according to format string & length."""
    return struct.unpack(fmt_type * length, file_desc.read(length))


@dataclass
class ImageHeader:
    """The seek location and value of a byte header."""

    offset: int
    bytes: tuple[bytes, ...]

    def compare(self, img: BinaryIO) -> bool:
        """Seek to a spot in a binary file and compare a byte array."""
        img.seek(self.offset)
        compare = unpack("c", len(self.bytes), img)
        return compare == self.bytes
