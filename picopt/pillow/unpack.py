"""Unpack items from a file descriptor."""
import struct

from typing import BinaryIO, Union


def unpack(
    fmt_type: str, length: int, file_desc: BinaryIO
) -> Union[tuple[bytes, ...], tuple[int]]:
    """Unpack information from a file according to format string & length."""
    return struct.unpack(fmt_type * length, file_desc.read(length))


def compare_header(img: BinaryIO, seek: int, byte_array: tuple[bytes, ...]) -> None:
    """Seek to a spot in a binary file and compare a byte array."""
    img.seek(seek)
    compare = unpack("c", len(byte_array), img)
    if compare != byte_array:
        raise ValueError(f"{compare} != {byte_array}")
