"""Test webp lossless detection via RIFF chunk parsing."""

from io import BytesIO
from struct import pack

from picopt.pillow.png_bit_depth import png_bit_depth
from picopt.pillow.webp_lossless import is_lossless
from tests import IMAGES_DIR

__all__ = ()

LOSSLESS_FN = "test_webp_lossless.webp"
LOSSY_FN = "test_webp_lossy.webp"
ANIMATED_FN = "test_animated_webp.webp"


def _chunk(fourcc: bytes, payload: bytes) -> bytes:
    data = fourcc + pack("<I", len(payload)) + payload
    if len(payload) % 2:
        data += b"\x00"
    return data


def _riff(*chunks: bytes) -> bytes:
    body = b"WEBP" + b"".join(chunks)
    return b"RIFF" + pack("<I", len(body)) + body


class TestWebPLossless:
    """Detection must be identical for file and in-memory input."""

    def test_real_fixtures_file_and_buffer_agree(self) -> None:
        for fn, expected in (
            (LOSSLESS_FN, True),
            (LOSSY_FN, False),
            (ANIMATED_FN, True),
        ):
            path = IMAGES_DIR / fn
            with path.open("rb") as f:
                assert is_lossless(f) == expected, fn
            assert is_lossless(BytesIO(path.read_bytes())) == expected, fn

    def test_lossless_with_large_icc_profile_in_buffer(self) -> None:
        """A big metadata chunk before VP8L must not defeat detection."""
        data = _riff(
            _chunk(b"VP8X", b"\x00" * 10),
            _chunk(b"ICCP", b"\x00" * 4096),
            _chunk(b"VP8L", b"\x2f" * 32),
        )
        assert is_lossless(BytesIO(data)) is True

    def test_lossy_with_metadata_containing_vp8l_bytes(self) -> None:
        """'VP8L' inside a metadata payload must not fake losslessness."""
        data = _riff(
            _chunk(b"VP8X", b"\x00" * 10),
            _chunk(b"EXIF", b"decoy VP8L decoy"),
            _chunk(b"VP8 ", b"\x00" * 32),
        )
        assert is_lossless(BytesIO(data)) is False

    def test_buffer_left_open_and_rewound(self) -> None:
        """The caller's buffer survives detection."""
        buffer = BytesIO((IMAGES_DIR / LOSSLESS_FN).read_bytes())
        is_lossless(buffer)
        assert not buffer.closed
        assert buffer.tell() == 0

    def test_empty_and_truncated_input(self) -> None:
        assert is_lossless(BytesIO(b"")) is False
        assert is_lossless(BytesIO(b"RIFF\x00\x00\x00\x00WEBP")) is False
        assert is_lossless(BytesIO(b"not a webp at all")) is False


class TestPngBitDepth:
    """Truncated PNGs must not report a fake bit depth."""

    def test_truncated_png_returns_none(self) -> None:
        header_only = (IMAGES_DIR / "test_png.png").read_bytes()[:16]
        assert png_bit_depth(BytesIO(header_only)) is None
