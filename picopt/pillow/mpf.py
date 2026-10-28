"""
Read and rewrite the MP Index of a multi-picture JPEG (MPO).

An MPO (CIPA DC-007) is a run of complete JPEGs: a primary image followed by
others, such as thumbnails, an HDR gain map or the other view of a stereo
pair. The primary carries an APP2 ``MPF`` segment: a TIFF header, then an IFD
whose MPEntry tag records each image's size and offset. Offsets count from
the TIFF header, not the start of the file, and the primary's is always zero.

Pillow reads this index but keeps the absolute offsets private and cannot
write a changed one back, so the segment is parsed here. Segments are walked
marker by marker from SOI to SOS, so a metadata payload that happens to
contain ``MPF`` can't pass for the index. This should be a part of Pillow.
"""

from __future__ import annotations

from dataclasses import dataclass
from struct import error as StructError  # noqa: N812
from struct import pack_into, unpack_from
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

_SOI: Final[bytes] = b"\xff\xd8"
_EOI: Final[bytes] = b"\xff\xd9"
_MARKER_PREFIX: Final[int] = 0xFF
_SOS: Final[int] = 0xDA
_APP1: Final[int] = 0xE1
_APP2: Final[int] = 0xE2
# Markers without a length field: TEM and RST0-RST7.
_STANDALONE_MARKERS: Final[frozenset[int]] = frozenset({0x01, *range(0xD0, 0xD8)})
# The marker and its two byte length.
_SEGMENT_HEADER_LEN: Final[int] = 4
_MPF_ID: Final[bytes] = b"MPF\x00"
_XMP_ID_PREFIX: Final[bytes] = b"http://ns.adobe.com/"
# The GContainer namespace, whatever prefix the XMP binds it to.
_GCONTAINER_NS: Final[bytes] = b"http://ns.google.com/photos/1.0/container/"
_BYTE_ORDERS: Final = {b"II*\x00": "<", b"MM\x00*": ">"}
_TAG_MP_ENTRY: Final[int] = 0xB002
_IFD_ENTRY_LEN: Final[int] = 12
_MP_ENTRY_LEN: Final[int] = 16
_MP_ENTRY_FORMAT: Final[str] = "IIIHH"
_MP_TYPE_MASK: Final[int] = 0xFFFFFF
_MP_TYPE_PRIMARY: Final[int] = 0x030000


class MpfError(ValueError):
    """The MP Index is missing, malformed, or doesn't match the file."""


@dataclass(frozen=True, slots=True)
class MpEntry:
    """One image's record in the MP Index."""

    attribute: int
    size: int
    offset: int
    dependent_1: int
    dependent_2: int

    @property
    def is_primary(self) -> bool:
        """Whether the entry is typed Baseline MP Primary Image."""
        return self.attribute & _MP_TYPE_MASK == _MP_TYPE_PRIMARY


@dataclass(frozen=True, slots=True)
class MpIndex:
    """The MP Index of an MPO and where its parts sit in the primary image."""

    segment_start: int
    segment_end: int
    tiff_start: int
    byte_order: str
    entries_start: int
    entries: tuple[MpEntry, ...]

    def absolute(self, number: int) -> int:
        """Return an image's offset from the start of the file."""
        if not number:
            return 0
        return self.tiff_start + self.entries[number].offset


def iter_segments(data: bytes) -> Iterator[tuple[int, int, int]]:
    """
    Yield ``(marker, start, end)`` for each JPEG segment from SOI to SOS.

    Stops quietly at the first byte that isn't a well formed segment.
    """
    if not data.startswith(_SOI):
        return
    pos = len(_SOI)
    while pos + _SEGMENT_HEADER_LEN <= len(data) and data[pos] == _MARKER_PREFIX:
        marker = data[pos + 1]
        if marker == _MARKER_PREFIX or marker in _STANDALONE_MARKERS:
            # A fill byte, or a marker with no payload.
            pos += 1 if marker == _MARKER_PREFIX else 2
            continue
        (length,) = unpack_from(">H", data, pos + 2)
        end = pos + 2 + length
        if length < 2 or end > len(data):  # noqa: PLR2004
            return
        yield marker, pos, end
        if marker == _SOS:
            return
        pos = end


def _find_mpf_segment(data: bytes) -> tuple[int, int] | None:
    for marker, start, end in iter_segments(data):
        if marker == _APP2 and data.startswith(_MPF_ID, start + _SEGMENT_HEADER_LEN):
            return start, end
    return None


def _unpack_entries(
    tiff: bytes, byte_order: str, table_offset: int, table_len: int
) -> tuple[MpEntry, ...]:
    if not table_len or table_len % _MP_ENTRY_LEN:
        msg = f"MPEntry table is {table_len} bytes"
        raise MpfError(msg)
    entry_format = byte_order + _MP_ENTRY_FORMAT
    return tuple(
        MpEntry(*unpack_from(entry_format, tiff, table_offset + pos))
        for pos in range(0, table_len, _MP_ENTRY_LEN)
    )


def _read_ifd(tiff: bytes) -> tuple[str, int, tuple[MpEntry, ...]]:
    """Return the byte order, the MPEntry table's offset, and its entries."""
    byte_order = _BYTE_ORDERS.get(tiff[:4])
    if byte_order is None:
        msg = "MPF segment has no TIFF header"
        raise MpfError(msg)
    (ifd_offset,) = unpack_from(byte_order + "I", tiff, 4)
    (tag_count,) = unpack_from(byte_order + "H", tiff, ifd_offset)
    for number in range(tag_count):
        tag_pos = ifd_offset + 2 + number * _IFD_ENTRY_LEN
        tag, _, table_len, table_offset = unpack_from(
            byte_order + "HHII", tiff, tag_pos
        )
        if tag == _TAG_MP_ENTRY:
            entries = _unpack_entries(tiff, byte_order, table_offset, table_len)
            return byte_order, table_offset, entries
    msg = "MPF segment has no MPEntry tag"
    raise MpfError(msg)


def parse(data: bytes) -> MpIndex | None:
    """Return the MP Index of the first image in ``data``, or None."""
    found = _find_mpf_segment(data)
    if found is None:
        return None
    segment_start, segment_end = found
    tiff_start = segment_start + _SEGMENT_HEADER_LEN + len(_MPF_ID)
    try:
        byte_order, table_offset, entries = _read_ifd(data[tiff_start:segment_end])
    except (MpfError, StructError):
        return None
    return MpIndex(
        segment_start=segment_start,
        segment_end=segment_end,
        tiff_start=tiff_start,
        byte_order=byte_order,
        entries_start=tiff_start + table_offset,
        entries=entries,
    )


def _is_complete(image: bytes) -> bool:
    """
    Report whether bytes hold one whole JPEG: headers through SOS, then EOI.

    A size in the MP Index goes stale when software that doesn't know the
    format grows a segment in front of it. A short slice still decodes, the
    missing rows filled with gray, so it has to be caught here.
    """
    return image.endswith(_EOI) and any(
        marker == _SOS for marker, _, _ in iter_segments(image)
    )


def _spans(data: bytes, index: MpIndex) -> tuple[tuple[int, int], ...]:
    """Return each image's ``(start, end)``: in order, in bounds, and whole."""
    spans: list[tuple[int, int]] = []
    previous_end = 0
    total = len(index.entries)
    for number, entry in enumerate(index.entries):
        start = index.absolute(number)
        end = start + entry.size
        if end > len(data):
            msg = f"image {number + 1} of {total} runs past the end of the file"
            raise MpfError(msg)
        if start < previous_end or not _is_complete(data[start:end]):
            msg = f"image {number + 1} of {total} isn't where the MP Index says"
            raise MpfError(msg)
        spans.append((start, end))
        previous_end = end
    return tuple(spans)


def split(data: bytes, index: MpIndex) -> tuple[bytes, ...]:
    """Return every image in the file, in MP Index order."""
    return tuple(data[start:end] for start, end in _spans(data, index))


def rebuild(data: bytes, index: MpIndex, images: Sequence[bytes]) -> bytes:
    """
    Replace each image with a new version and rewrite the MP Index to match.

    The bytes between and after the images (padding, or data appended by
    other software) are kept in place around them. ``images[0]`` must still
    carry its MPF segment. Size and offset fields are fixed width, so
    rewriting them never moves anything.
    """
    spans = _spans(data, index)
    if len(images) != len(spans):
        msg = f"{len(images)} images for an MP Index of {len(spans)}"
        raise MpfError(msg)
    new_index = parse(images[0])
    if new_index is None or len(new_index.entries) != len(spans):
        msg = "rewritten primary image lost its MP Index"
        raise MpfError(msg)
    output = bytearray()
    starts: list[int] = []
    previous_end = 0
    for image, (start, end) in zip(images, spans, strict=True):
        output += data[previous_end:start]
        starts.append(len(output))
        output += image
        previous_end = end
    output += data[previous_end:]
    entry_format = new_index.byte_order + _MP_ENTRY_FORMAT
    for number, entry in enumerate(new_index.entries):
        offset = starts[number] - new_index.tiff_start if number else 0
        pos = new_index.entries_start + number * _MP_ENTRY_LEN
        fields = (len(images[number]), offset, entry.dependent_1, entry.dependent_2)
        pack_into(entry_format, output, pos, entry.attribute, *fields)
    return bytes(output)


def _others_missing(data: bytes, index: MpIndex, number: int) -> bool:
    """Report whether every image but one is gone from where the index says."""
    return not any(
        data.startswith(_SOI, index.absolute(other))
        for other in range(len(index.entries))
        if other != number
    )


def primary(data: bytes, index: MpIndex) -> bytes:
    """
    Return the primary image: the one typed primary, else the first.

    When every other image is gone, the primary runs to the end of the file,
    whatever size the index gives it. Older picopt wrote exactly that: the
    primary alone, still carrying the index of the images it dropped.
    """
    number = next(
        (number for number, entry in enumerate(index.entries) if entry.is_primary), 0
    )
    start = index.absolute(number)
    image = data[start : start + index.entries[number].size]
    if _is_complete(image):
        return image
    if _others_missing(data, index, number) and _is_complete(data[start:]):
        return data[start:]
    msg = "primary image isn't where the MP Index says"
    raise MpfError(msg)


def strip(jpeg: bytes) -> bytes:
    """Remove the MPF segment from a JPEG, if it has one."""
    found = _find_mpf_segment(jpeg)
    if found is None:
        return jpeg
    start, end = found
    return jpeg[:start] + jpeg[end:]


def has_gcontainer(jpeg: bytes) -> bool:
    """
    Report whether a JPEG's XMP uses the GContainer namespace.

    A GContainer directory (Ultra HDR, Motion Photo) records the byte length
    of each item appended to the file, so resizing any of them breaks it.
    """
    return any(
        marker == _APP1
        and jpeg.startswith(_XMP_ID_PREFIX, start + _SEGMENT_HEADER_LEN)
        and _GCONTAINER_NS in jpeg[start:end]
        for marker, start, end in iter_segments(jpeg)
    )
