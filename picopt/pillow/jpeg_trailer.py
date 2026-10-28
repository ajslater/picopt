"""
Keep the data appended after a JPEG's end of image.

Phones append whole files after the EOI marker of the photo they save: an
Android Ultra HDR photo its gain map JPEG, a Google Motion Photo an MP4,
Samsung a trailer of its own. A JPEG decoder stops at the first EOI, and so
does mozjpeg, so recompressing the photo alone would drop them.

The XMP of an Ultra HDR or Motion Photo records each appended item's length,
and older Motion Photos the video's offset from the end of the file. Those
still hold when the photo shrinks, so long as the appended bytes are kept
as they are. An MP Index, which Ultra HDR also carries, doesn't: it records
the primary image's size and each other image's offset from the index
itself, so :mod:`picopt.pillow.mpf` rewrites it.

The image is walked marker by marker, past each scan's entropy coded data,
the way libjpeg reads it. An EOI inside a segment payload, like that of an
EXIF thumbnail, can't end it early. This should be a part of Pillow.
"""

from __future__ import annotations

import re
from struct import unpack_from
from typing import TYPE_CHECKING, Final

from picopt.pillow import mpf

if TYPE_CHECKING:
    from collections.abc import Iterator

_SOI: Final[bytes] = b"\xff\xd8"
_SOI_MARKER: Final[int] = 0xD8
_EOI_MARKER: Final[int] = 0xD9
_SOS: Final[int] = 0xDA
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


def _iter_markers(data: bytes) -> Iterator[tuple[int, int]]:
    """
    Yield ``(marker, end)`` for each marker of the first image.

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
        yield marker, end
        if marker == _EOI_MARKER:
            return
        pattern = _SCAN_END if marker == _SOS else _NEXT_MARKER
        pos = end


def image_end(data: bytes) -> int | None:
    """Return the offset just past the first image's EOI, or None if it has none."""
    for marker, end in _iter_markers(data):
        if marker == _EOI_MARKER:
            return end
    return None


def rejoin(data: bytes, end: int, image: bytes) -> bytes:
    """
    Put a recompressed first image back in front of the data that followed it.

    ``data[:end]`` is the original first image and ``image`` its new version.
    If the original has an MP Index, ``image`` must keep it, and the index
    must give the first image's size and find each other image, whole, after
    it. Raises :class:`~picopt.pillow.mpf.MpfError` otherwise.
    """
    index = mpf.parse(data)
    if index is None:
        if mpf.has_index(data):
            msg = "its MP Index is unreadable"
            raise mpf.MpfError(msg)
        return image + data[end:]
    primary, *others = mpf.split(data, index)
    if len(primary) != end:
        msg = "its MP Index doesn't give the first image's size"
        raise mpf.MpfError(msg)
    return mpf.rebuild(data, index, (image, *others))
