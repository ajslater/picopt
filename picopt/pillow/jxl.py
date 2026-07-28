"""
JPEG XL support: PIL registration and lossless detection.

Importing this module registers the ``pillow-jxl-plugin`` codec with Pillow
(the plugin registers itself as an import side effect) and patches in a
``save_all`` handler the plugin does not install itself. picopt's
``ImageHandler.pil_save`` always calls ``Image.save(save_all=True)``, which
raises ``KeyError`` for any format missing from Pillow's ``SAVE_ALL``
registry. JPEG XL animation is not supported by the plugin at all, so
reusing the single-frame save handler is exactly right.

The rest of this module answers one question detect_format needs and the
plugin cannot: may picopt losslessly re-encode this JXL? That is false for
two unrelated reasons, and the caller does not care which:

* **XYB-encoded (lossy) files.** Re-encoding them losslessly is safe for
  pixels but pointless — the result is always far larger and gets discarded
  by the size gate — so it is wasted work on every run.
* **JPEG-reconstruction files.** A JXL carrying a ``jbrd`` box can restore
  its source JPEG byte for byte. Re-encoding preserves the pixels but drops
  that box, silently destroying the reconstruction data.

Neither signal is exposed by the plugin's decoder, so the codestream header
is parsed here. This should be a part of Pillow.
"""

from __future__ import annotations

from contextlib import suppress
from importlib import import_module
from typing import TYPE_CHECKING, Final

from PIL import Image

if TYPE_CHECKING:
    from typing import BinaryIO

# Imported for its side effect alone: pillow_jxl registers the codec with
# Pillow at import time and exposes nothing picopt calls directly, so a plain
# `import` reads as unused and gets stripped by autofixers.
# Suppressed so picopt still runs when the optional codec is absent; the
# handlers then probe as unavailable and JXL files are simply skipped.
with suppress(ImportError):
    import_module("pillow_jxl")

JXL_FORMAT_STR: Final[str] = "JXL"

# Pillow's own registry is the source of truth for whether the import above
# succeeded.
if JXL_FORMAT_STR in Image.SAVE and JXL_FORMAT_STR not in Image.SAVE_ALL:
    Image.register_save_all(JXL_FORMAT_STR, Image.SAVE[JXL_FORMAT_STR])

_CODESTREAM_SIG: Final[bytes] = b"\xff\x0a"
_CONTAINER_SIG: Final[bytes] = b"\x00\x00\x00\x0cJXL \x0d\x0a\x87\x0a"
_JPEG_RECONSTRUCTION_BOX: Final[bytes] = b"jbrd"
_BROTLI_BOX: Final[bytes] = b"brob"
_CODESTREAM_BOX: Final[bytes] = b"jxlc"
_PARTIAL_CODESTREAM_BOX: Final[bytes] = b"jxlp"
# The partial-codestream box prefixes its payload with a 4 byte sequence index.
_JXLP_INDEX_LEN: Final[int] = 4
_BOX_HEADER_LEN: Final[int] = 8
_BOX_EXT_HEADER_LEN: Final[int] = 16
# The image header is a few dozen bytes; this is a generous ceiling that also
# bounds how much of a split codestream is buffered.
_MAX_HEADER_BYTES: Final[int] = 1024
# A sanity bound: JXL permits at most 256 extra channels, and a parse that
# claims more has certainly desynchronized.
_MAX_EXTRA_CHANNELS: Final[int] = 256

# U32 field distributions, as (bits, offset) pairs or a bare literal value.
# A 2 bit selector chooses among the four alternatives.
_U32_DIMENSION: Final = ((9, 1), (13, 1), (18, 1), (30, 1))
_U32_ENUM: Final = (0, 1, 2, (6, 3))
_U32_BITS_PER_SAMPLE: Final = (8, 10, 12, (6, 1))
_U32_FLOAT_BITS_PER_SAMPLE: Final = (32, 16, 24, (6, 1))
_U32_NUM_EXTRA_CHANNELS: Final = (0, 1, (4, 2), (12, 1))
_U32_DIM_SHIFT: Final = (0, 3, 4, (3, 1))
_U32_NAME_LEN: Final = (0, (4, 1), (5, 17), (10, 49))
_U32_PREVIEW_DIV8: Final = (16, 32, (5, 1), (9, 33))
_U32_PREVIEW: Final = ((6, 1), (8, 65), (10, 321), (12, 1345))
_U32_TPS_NUMERATOR: Final = (100, 1000, (10, 1), (30, 1))
_U32_TPS_DENOMINATOR: Final = (1, 1001, (8, 1), (10, 1))
_U32_NUM_LOOPS: Final = (0, (3, 0), (16, 0), (32, 0))
_U32_CFA_CHANNEL: Final = (1, (2, 0), (4, 3), (8, 19))

_EXTRA_CHANNEL_ALPHA: Final[int] = 0
_EXTRA_CHANNEL_SPOT_COLOR: Final[int] = 3
_EXTRA_CHANNEL_CFA: Final[int] = 4
_SPOT_COLOR_BITS: Final[int] = 32 * 4


class _TruncatedError(Exception):
    """The header ended before the parse finished."""


class _BitReader:
    """Reads the JXL bitstream, which packs bits LSB-first within each byte."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def bit(self) -> int:
        """Read a single bit."""
        byte_index, bit_index = divmod(self._pos, 8)
        if byte_index >= len(self._data):
            raise _TruncatedError
        self._pos += 1
        return (self._data[byte_index] >> bit_index) & 1

    def bits(self, count: int) -> int:
        """Read an unsigned integer of ``count`` bits."""
        value = 0
        for index in range(count):
            value |= self.bit() << index
        return value

    def u32(self, distributions: tuple) -> int:
        """Read a U32: a 2 bit selector picks one of four encodings."""
        distribution = distributions[self.bits(2)]
        if isinstance(distribution, int):
            return distribution
        bit_count, offset = distribution
        return self.bits(bit_count) + offset


def _skip_size_header(reader: _BitReader) -> None:
    small = reader.bit()
    if small:
        reader.bits(5)
    else:
        reader.u32(_U32_DIMENSION)
    if reader.bits(3) == 0:
        if small:
            reader.bits(5)
        else:
            reader.u32(_U32_DIMENSION)


def _skip_preview_header(reader: _BitReader) -> None:
    div8 = reader.bit()
    distributions = _U32_PREVIEW_DIV8 if div8 else _U32_PREVIEW
    reader.u32(distributions)
    if reader.bits(3) == 0:
        reader.u32(distributions)


def _skip_animation_header(reader: _BitReader) -> None:
    reader.u32(_U32_TPS_NUMERATOR)
    reader.u32(_U32_TPS_DENOMINATOR)
    reader.u32(_U32_NUM_LOOPS)
    reader.bit()  # have_timecodes


def _skip_bit_depth(reader: _BitReader) -> None:
    if reader.bit():  # floating point
        reader.u32(_U32_FLOAT_BITS_PER_SAMPLE)
        reader.bits(4)  # exponent bits - 1
    else:
        reader.u32(_U32_BITS_PER_SAMPLE)


def _skip_extra_channel_info(reader: _BitReader) -> None:
    if reader.bit():  # all default: an 8 bit alpha channel
        return
    channel_type = reader.u32(_U32_ENUM)
    _skip_bit_depth(reader)
    reader.u32(_U32_DIM_SHIFT)
    reader.bits(8 * reader.u32(_U32_NAME_LEN))  # name
    if channel_type == _EXTRA_CHANNEL_ALPHA:
        reader.bit()  # alpha_associated
    elif channel_type == _EXTRA_CHANNEL_SPOT_COLOR:
        reader.bits(_SPOT_COLOR_BITS)
    elif channel_type == _EXTRA_CHANNEL_CFA:
        reader.u32(_U32_CFA_CHANNEL)


def _skip_extra_fields(reader: _BitReader) -> None:
    reader.bits(3)  # orientation
    if reader.bit():
        _skip_size_header(reader)  # intrinsic size
    if reader.bit():
        _skip_preview_header(reader)
    if reader.bit():
        _skip_animation_header(reader)


def _is_xyb_encoded(codestream: bytes) -> bool | None:
    """
    Parse the image header far enough to read the ``xyb_encoded`` flag.

    XYB is a lossy colour transform, so an XYB-encoded file cannot be
    lossless. Returns None when the header cannot be parsed, which the
    caller treats as "do not touch this file".
    """
    if not codestream.startswith(_CODESTREAM_SIG):
        return None
    reader = _BitReader(codestream[len(_CODESTREAM_SIG) :])
    try:
        _skip_size_header(reader)
        if reader.bit():  # ImageMetadata all_default; xyb_encoded defaults true
            return True
        if reader.bit():  # extra_fields
            _skip_extra_fields(reader)
        _skip_bit_depth(reader)
        reader.bit()  # modular_16bit_buffers
        extra_channel_count = reader.u32(_U32_NUM_EXTRA_CHANNELS)
        if extra_channel_count > _MAX_EXTRA_CHANNELS:
            return None
        for _ in range(extra_channel_count):
            _skip_extra_channel_info(reader)
    except (_TruncatedError, IndexError):
        return None
    else:
        return bool(reader.bit())


def _read_box_header(buffer: BinaryIO) -> tuple[bytes, int, int] | None:
    """Return (box_type, total_box_size, header_length) or None at the end."""
    header = buffer.read(_BOX_HEADER_LEN)
    if len(header) < _BOX_HEADER_LEN:
        return None
    size = int.from_bytes(header[:4], "big")
    box_type = header[4:8]
    header_len = _BOX_HEADER_LEN
    if size == 1:
        extended = buffer.read(_BOX_EXT_HEADER_LEN - _BOX_HEADER_LEN)
        if len(extended) < _BOX_EXT_HEADER_LEN - _BOX_HEADER_LEN:
            return None
        size = int.from_bytes(extended, "big")
        header_len = _BOX_EXT_HEADER_LEN
    if size and size < header_len:
        return None
    return box_type, size, header_len


def _walk_container(buffer: BinaryIO) -> tuple[bytes, bool]:
    """
    Walk the ISO BMFF boxes, returning (codestream_head, has_reconstruction).

    Payloads are skipped with seeks; only the leading codestream bytes are
    buffered, and only up to the header ceiling.
    """
    codestream = b""
    has_reconstruction = False
    buffer.seek(len(_CONTAINER_SIG))
    while True:
        box = _read_box_header(buffer)
        if box is None:
            break
        box_type, size, header_len = box
        payload_start = buffer.tell()
        if box_type == _JPEG_RECONSTRUCTION_BOX:
            has_reconstruction = True
        elif box_type == _BROTLI_BOX:
            # A brotli-compressed box names its inner type in the first four
            # payload bytes.
            has_reconstruction = has_reconstruction or (
                buffer.read(4) == _JPEG_RECONSTRUCTION_BOX
            )
        elif box_type in (_CODESTREAM_BOX, _PARTIAL_CODESTREAM_BOX) and (
            len(codestream) < _MAX_HEADER_BYTES
        ):
            if box_type == _PARTIAL_CODESTREAM_BOX:
                buffer.seek(payload_start + _JXLP_INDEX_LEN)
            codestream += buffer.read(_MAX_HEADER_BYTES - len(codestream))
        if size == 0:
            # A zero size means the box runs to the end of the file.
            break
        buffer.seek(payload_start + size - header_len)
    return codestream, has_reconstruction


def is_lossless(input_buffer: BinaryIO) -> bool:
    """
    Report whether picopt may losslessly re-encode this JXL.

    False for lossy (XYB-encoded) files, for files carrying JPEG
    reconstruction data, and for anything that cannot be parsed. Leaves the
    buffer position at 0; the caller owns closing it.
    """
    try:
        input_buffer.seek(0)
        signature = input_buffer.read(len(_CONTAINER_SIG))
        if signature.startswith(_CODESTREAM_SIG):
            input_buffer.seek(0)
            codestream = input_buffer.read(_MAX_HEADER_BYTES)
            has_reconstruction = False
        elif signature == _CONTAINER_SIG:
            codestream, has_reconstruction = _walk_container(input_buffer)
        else:
            return False
        if has_reconstruction:
            return False
        return _is_xyb_encoded(codestream) is False
    finally:
        input_buffer.seek(0)
