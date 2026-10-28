"""
Keep the data appended after a JPEG's end of image.

Phones append whole files after the EOI marker of the photo they save: an
Android Ultra HDR photo its gain map JPEG, a Google Motion Photo an MP4,
Samsung a trailer of its own. A JPEG decoder stops at the first EOI, and so
does mozjpeg, so recompressing the photo alone would drop them.

The XMP of an Ultra HDR or Motion Photo records each appended item's length,
and older Motion Photos the video's offset from the end of the file. Those
still hold when the photo shrinks, so long as the appended bytes are kept
as they are. An MP Index (CIPA DC-007) in the photo's APP2 ``MPF`` segment,
which Ultra HDR also carries, doesn't: it records the primary image's size
and each other image's offset from the index itself, so it's rewritten.

The image is walked marker by marker, past each scan's entropy coded data,
the way libjpeg reads it. An EOI inside a segment payload, like that of an
EXIF thumbnail, can't end it early. This should be a part of Pillow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from struct import error as StructError  # noqa: N812
from struct import pack_into, unpack_from
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterator

_SOI: Final[bytes] = b"\xff\xd8"
_SOI_MARKER: Final[int] = 0xD8
_EOI_MARKER: Final[int] = 0xD9
_SOS: Final[int] = 0xDA
_APP2: Final[int] = 0xE2
# Markers without a length field: TEM, RST0-RST7 and EOI.
_STANDALONE_MARKERS: Final[frozenset[int]] = frozenset(
    {0x01, *range(0xD0, 0xD8), _EOI_MARKER}
)
# The next marker: 0xFF and a code, skipping fill bytes (more 0xFF) and any
# garbage before it, as libjpeg does. In entropy coded data 0xFF 0x00 is a
# stuffed byte and a restart marker doesn't end the scan.
_NEXT_MARKER: Final = re.compile(rb"\xff[^\x00\xff]")
_SCAN_END: Final = re.compile(rb"\xff[^\x00\xd0-\xd7\xff]")
# The marker and its two byte length.
_SEGMENT_HEADER_LEN: Final[int] = 4
_MPF_ID: Final[bytes] = b"MPF\x00"
_BYTE_ORDERS: Final = {b"II*\x00": "<", b"MM\x00*": ">"}
_TAG_MP_ENTRY: Final[int] = 0xB002
_IFD_ENTRY_LEN: Final[int] = 12
_MP_ENTRY_LEN: Final[int] = 16
# Each MPEntry's size and offset, between its attribute and dependent images.
_MP_ENTRY_SIZE_OFFSET: Final[str] = "II"
_MP_ENTRY_SIZE_POS: Final[int] = 4


class JpegTrailerError(ValueError):
    """The MP Index doesn't match the images that follow the first."""


@dataclass(frozen=True, slots=True)
class _MpIndex:
    """Where an MP Index sits in a file and the size and offset of each image."""

    tiff_start: int
    byte_order: str
    entries_start: int
    entries: tuple[tuple[int, int], ...]


def _segment_end(data: bytes, start: int) -> int | None:
    """Return where the segment at ``start`` ends, or None if it's malformed."""
    marker = data[start + 1]
    if marker in _STANDALONE_MARKERS:
        return start + 2
    if marker == _SOI_MARKER or start + _SEGMENT_HEADER_LEN > len(data):
        return None
    (length,) = unpack_from(">H", data, start + 2)
    end = start + 2 + length
    if length < 2 or end > len(data):  # noqa: PLR2004
        return None
    return end


def _iter_markers(data: bytes) -> Iterator[tuple[int, int, int]]:
    """
    Yield ``(marker, start, end)`` for each marker of the first image.

    Stops after its EOI, or quietly at the first malformed segment.
    """
    if not data.startswith(_SOI):
        return
    pattern = _NEXT_MARKER
    pos = len(_SOI)
    while match := pattern.search(data, pos):
        start = match.start()
        marker = data[start + 1]
        end = _segment_end(data, start)
        if end is None:
            return
        yield marker, start, end
        if marker == _EOI_MARKER:
            return
        pattern = _SCAN_END if marker == _SOS else _NEXT_MARKER
        pos = end


def image_end(data: bytes) -> int | None:
    """Return the offset just past the first image's EOI, or None if it has none."""
    for marker, _, end in _iter_markers(data):
        if marker == _EOI_MARKER:
            return end
    return None


def _find_mp_entry_table(tiff: bytes, byte_order: str) -> tuple[int, int]:
    """Return the MPEntry table's length and offset from the TIFF header."""
    (ifd_offset,) = unpack_from(byte_order + "I", tiff, 4)
    (tag_count,) = unpack_from(byte_order + "H", tiff, ifd_offset)
    for number in range(tag_count):
        tag_pos = ifd_offset + 2 + number * _IFD_ENTRY_LEN
        tag, _, table_len, table_offset = unpack_from(
            byte_order + "HHII", tiff, tag_pos
        )
        if tag == _TAG_MP_ENTRY:
            return table_len, table_offset
    msg = "its MPF segment has no MPEntry tag"
    raise JpegTrailerError(msg)


def _read_mp_index(data: bytes, tiff_start: int, segment_end: int) -> _MpIndex:
    tiff = data[tiff_start:segment_end]
    byte_order = _BYTE_ORDERS.get(tiff[:4])
    if byte_order is None:
        msg = "its MPF segment has no TIFF header"
        raise JpegTrailerError(msg)
    table_len, table_offset = _find_mp_entry_table(tiff, byte_order)
    if not table_len or table_len % _MP_ENTRY_LEN:
        msg = f"its MPEntry table is {table_len} bytes"
        raise JpegTrailerError(msg)
    entry_format = byte_order + _MP_ENTRY_SIZE_OFFSET
    entries = tuple(
        unpack_from(entry_format, tiff, pos + _MP_ENTRY_SIZE_POS)
        for pos in range(table_offset, table_offset + table_len, _MP_ENTRY_LEN)
    )
    return _MpIndex(tiff_start, byte_order, tiff_start + table_offset, entries)


def _mp_index(data: bytes) -> _MpIndex | None:
    """Return the MP Index in the first image's header, if it has one."""
    for marker, start, end in _iter_markers(data):
        if marker == _SOS:
            break
        if marker == _APP2 and data.startswith(_MPF_ID, start + _SEGMENT_HEADER_LEN):
            tiff_start = start + _SEGMENT_HEADER_LEN + len(_MPF_ID)
            try:
                return _read_mp_index(data, tiff_start, end)
            except StructError as exc:
                msg = "its MPF segment is truncated"
                raise JpegTrailerError(msg) from exc
    return None


def rejoin(data: bytes, end: int, image: bytes) -> bytes:
    """
    Put a recompressed first image back in front of the data that followed it.

    ``data[:end]`` is the original first image and ``image`` its new version.
    If the original has an MP Index, ``image`` must keep it, and every image
    it lists after the first must lie in ``data[end:]``. Size and offset
    fields are fixed width, so rewriting them never moves anything.
    """
    trailer = data[end:]
    index = _mp_index(data)
    if index is None:
        return image + trailer
    new_index = _mp_index(image)
    if new_index is None or len(new_index.entries) != len(index.entries):
        msg = "recompressing it lost its MP Index"
        raise JpegTrailerError(msg)
    output = bytearray(image + trailer)
    entry_format = new_index.byte_order + _MP_ENTRY_SIZE_OFFSET
    total = len(index.entries)
    for number, (size, offset) in enumerate(index.entries):
        if number:
            start = index.tiff_start + offset
            if start < end or start + size > len(data):
                msg = (
                    f"its MP Index puts image {number + 1} of {total} "
                    "outside the data after the first image"
                )
                raise JpegTrailerError(msg)
            new_size = size
            new_offset = len(image) + start - end - new_index.tiff_start
        elif offset:
            msg = "its MP Index doesn't start with the first image"
            raise JpegTrailerError(msg)
        else:
            new_size, new_offset = len(image), 0
        pos = new_index.entries_start + number * _MP_ENTRY_LEN + _MP_ENTRY_SIZE_POS
        pack_into(entry_format, output, pos, new_size, new_offset)
    return bytes(output)
