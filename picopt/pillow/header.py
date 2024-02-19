"""Unpack items from a file descriptor."""
from dataclasses import dataclass
from mmap import mmap
from typing import BinaryIO


@dataclass
class ImageHeader:
    """The seek location and value of a byte header."""

    offset: int
    compare_bytes: bytes

    def compare(self, img: BinaryIO | mmap) -> bool:
        """Seek to a spot in a binary file and compare a byte array."""
        img.seek(self.offset)
        compare = img.read(len(self.compare_bytes))
        return compare == self.compare_bytes
