"""Unpack items from a file descriptor."""
import struct

from typing import BinaryIO, Tuple, Union


def unpack(
    fmt_type: str, length: int, file_desc: BinaryIO
) -> Union[Tuple[bytes, ...], Tuple[int]]:
    """Unpack information from a file according to format string & length."""
    return struct.unpack(fmt_type * length, file_desc.read(length))
