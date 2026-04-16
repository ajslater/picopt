"""Unpack items from a file descriptor."""

from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    import picopt.pillow.webp_lossless

from dataclasses import dataclass
from mmap import mmap


@dataclass
class ImageHeader:
    """The seek location and value of a byte header."""

    offset: int
    compare_bytes: bytes

    def compare(
        self: "picopt.pillow.webp_lossless.ImageHeader", img: BinaryIO | mmap
    ) -> bool:
        """Seek to a spot in a binary file and compare a byte array."""
        img.seek(self.offset)
        compare = img.read(len(self.compare_bytes))
        return compare == self.compare_bytes
