"""Unit tests for the MP Index parser and rewriter."""

import struct
from io import BytesIO

import pytest
from PIL import Image

from picopt.pillow import mpf
from tests import IMAGES_DIR
from tests.mpo_util import CAMERA_MPO, CONTAINER_XMP, build_mpo, jpeg

__all__ = ()

_PRIMARY = jpeg((40, 30), (200, 20, 20))
_SECONDARY = jpeg((20, 16), (10, 200, 10))


def _with_segment(image: bytes, marker: int, payload: bytes) -> bytes:
    """Insert a segment right after SOI."""
    segment = bytes((0xFF, marker)) + struct.pack(">H", len(payload) + 2) + payload
    return image[:2] + segment + image[2:]


def _index(data: bytes) -> mpf.MpIndex:
    index = mpf.parse(data)
    assert index is not None
    return index


class TestParse:
    def test_matches_pillow(self) -> None:
        data = CAMERA_MPO.read_bytes()
        index = _index(data)
        with Image.open(CAMERA_MPO) as image:
            entries = image.mpinfo[0xB002]  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]
            offsets = image._MpoImageFile__mpoffsets  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]
        assert index.byte_order == "<"
        assert [entry.size for entry in index.entries] == [e["Size"] for e in entries]
        assert [index.absolute(n) for n in range(len(entries))] == offsets
        assert [entry.is_primary for entry in index.entries] == [True, False]

    @pytest.mark.parametrize("byte_order", ["<", ">"])
    def test_byte_orders(self, byte_order: str) -> None:
        data = build_mpo([_PRIMARY, _SECONDARY], byte_order=byte_order)
        index = _index(data)
        assert index.byte_order == byte_order
        primary, secondary = mpf.split(data, index)
        assert mpf.strip(primary) == _PRIMARY
        assert secondary == _SECONDARY

    def test_plain_jpeg(self) -> None:
        assert mpf.parse((IMAGES_DIR / "test_jpg.jpg").read_bytes()) is None

    def test_not_a_jpeg(self) -> None:
        assert mpf.parse(b"MPF\x00II*\x00\x08\x00\x00\x00") is None

    @pytest.mark.parametrize("marker", [0xE1, 0xFE])
    def test_mpf_payload_in_another_segment(self, marker: int) -> None:
        mpo = build_mpo([_PRIMARY, _SECONDARY])
        segment_end = _index(mpo).segment_end
        # The real index, moved into an APP1 or COM segment, isn't an index.
        data = _with_segment(_PRIMARY, marker, mpo[6:segment_end])
        assert mpf.parse(data) is None

    @pytest.mark.parametrize(
        "payload",
        [
            b"MPF\x00II*\x00\x08\x00\x00\x00",  # TIFF header, no IFD
            b"MPF\x00XXXX\x08\x00\x00\x00\x00\x00",  # no TIFF header
            b"MPF\x00II*\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00",  # no MPEntry
        ],
    )
    def test_malformed(self, payload: bytes) -> None:
        assert mpf.parse(_with_segment(_PRIMARY, 0xE2, payload)) is None

    def test_fill_bytes_before_a_marker(self) -> None:
        mpo = build_mpo([_PRIMARY, _SECONDARY])
        assert mpf.parse(mpo[:2] + b"\xff\xff" + mpo[2:]) is not None


class TestSplit:
    def test_image_past_the_end(self) -> None:
        data = build_mpo([_PRIMARY, _SECONDARY])
        truncated = data[:-10]
        with pytest.raises(mpf.MpfError, match="image 2 of 2 runs past the end"):
            mpf.split(truncated, _index(truncated))

    def test_image_not_where_the_index_says(self) -> None:
        data = build_mpo([_PRIMARY, _SECONDARY], gap=b"\x00" * 4, trailer=b"tail")
        primary_size = _index(data).entries[0].size
        # Drop a padding byte: the second image now starts a byte early.
        shifted = data[:primary_size] + data[primary_size + 1 :]
        with pytest.raises(mpf.MpfError, match="image 2 of 2 isn't where"):
            mpf.split(shifted, _index(shifted))

    def test_stale_primary_size(self) -> None:
        """
        Software that doesn't know MPF grew a segment before the index.

        Offsets count from the index, so only the primary's size went stale.
        Cutting the primary there would lose the bottom of the photo.
        """
        edited = _with_segment(build_mpo([_PRIMARY, _SECONDARY]), 0xFE, b"edit")
        with pytest.raises(mpf.MpfError, match="image 1 of 2 isn't where"):
            mpf.split(edited, _index(edited))


class TestRebuild:
    @pytest.mark.parametrize("byte_order", ["<", ">"])
    def test_rewrites_sizes_and_offsets(self, byte_order: str) -> None:
        data = build_mpo([_PRIMARY, _SECONDARY], byte_order=byte_order)
        index = _index(data)
        primary, _ = mpf.split(data, index)
        bigger_primary = _with_segment(primary, 0xFE, b"a comment")
        smaller_secondary = jpeg((8, 8), (0, 0, 255))
        rebuilt = mpf.rebuild(data, index, (bigger_primary, smaller_secondary))
        new_primary, new_secondary = mpf.split(rebuilt, _index(rebuilt))
        # Only the index's own fields changed in the primary.
        assert len(new_primary) == len(bigger_primary)
        assert mpf.strip(new_primary) == mpf.strip(bigger_primary)
        assert new_secondary == smaller_secondary
        with Image.open(BytesIO(rebuilt)) as image:
            assert image.format == "MPO"
            sizes = []
            for frame in range(image.n_frames):  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]
                image.seek(frame)
                image.load()
                sizes.append(image.size)
        assert sizes == [(40, 30), (8, 8)]

    def test_keeps_gaps_and_trailer(self) -> None:
        gap, trailer = b"\x00" * 7, b"appended by another program"
        data = build_mpo([_PRIMARY, _SECONDARY], gap=gap, trailer=trailer)
        index = _index(data)
        primary, _ = mpf.split(data, index)
        new_secondary = jpeg((8, 8), (0, 0, 255))
        rebuilt = mpf.rebuild(data, index, (primary, new_secondary))
        assert mpf.split(rebuilt, _index(rebuilt))[1] == new_secondary
        assert rebuilt.endswith(new_secondary + trailer)
        assert rebuilt[len(primary) : len(primary) + len(gap)] == gap

    def test_same_images_same_bytes(self) -> None:
        data = CAMERA_MPO.read_bytes()
        index = _index(data)
        assert mpf.rebuild(data, index, mpf.split(data, index)) == data

    def test_image_count_mismatch(self) -> None:
        data = build_mpo([_PRIMARY, _SECONDARY])
        index = _index(data)
        with pytest.raises(mpf.MpfError, match="1 images for an MP Index of 2"):
            mpf.rebuild(data, index, mpf.split(data, index)[:1])

    def test_primary_lost_its_index(self) -> None:
        data = build_mpo([_PRIMARY, _SECONDARY])
        index = _index(data)
        with pytest.raises(mpf.MpfError, match="lost its MP Index"):
            mpf.rebuild(data, index, (_PRIMARY, _SECONDARY))


class TestPrimary:
    def test_typed_primary(self) -> None:
        data = build_mpo([_PRIMARY, _SECONDARY])
        index = _index(data)
        assert mpf.primary(data, index) == mpf.split(data, index)[0]

    def test_declared_past_the_end_but_complete(self) -> None:
        """Older picopt kept the index but dropped the images after the first."""
        data = build_mpo([_PRIMARY, _SECONDARY])
        primary = mpf.split(data, _index(data))[0]
        # Drop the JFIF segment under the unchanged index, and the image after.
        assert _PRIMARY[2:4] == b"\xff\xe0"
        jfif_end = 4 + struct.unpack(">H", _PRIMARY[4:6])[0]
        index_end = len(primary) - len(_PRIMARY) + 2
        shrunk = primary[:index_end] + _PRIMARY[jfif_end:]
        assert len(shrunk) < len(primary)
        assert mpf.primary(shrunk, _index(shrunk)) == shrunk

    def test_truncated(self) -> None:
        data = build_mpo([_PRIMARY, _SECONDARY])
        truncated = data[: len(_PRIMARY) // 2]
        with pytest.raises(mpf.MpfError, match="primary image isn't where"):
            mpf.primary(truncated, _index(truncated))

    def test_stale_size(self) -> None:
        """A size gone stale under an edit by other software isn't trusted."""
        edited = _with_segment(build_mpo([_PRIMARY, _SECONDARY]), 0xFE, b"edit")
        with pytest.raises(mpf.MpfError, match="primary image isn't where"):
            mpf.primary(edited, _index(edited))

    def test_alone_and_longer_than_declared(self) -> None:
        """Older picopt could also write a primary bigger than its index says."""
        data = build_mpo([_PRIMARY, _SECONDARY])
        primary = mpf.split(data, _index(data))[0]
        grown = _with_segment(primary, 0xFE, b"a JFIF segment, say")
        assert mpf.primary(grown, _index(grown)) == grown


class TestStrip:
    def test_removes_only_the_index(self) -> None:
        data = build_mpo([_PRIMARY, _SECONDARY])
        primary = mpf.split(data, _index(data))[0]
        stripped = mpf.strip(primary)
        assert stripped == _PRIMARY
        assert mpf.parse(stripped) is None

    def test_no_index(self) -> None:
        assert mpf.strip(_PRIMARY) == _PRIMARY


class TestGContainer:
    @staticmethod
    def _xmp(xmp: bytes) -> bytes:
        return b"http://ns.adobe.com/xap/1.0/\x00" + xmp

    def test_in_xmp(self) -> None:
        assert mpf.has_gcontainer(
            _with_segment(_PRIMARY, 0xE1, self._xmp(CONTAINER_XMP))
        )

    def test_plain_xmp(self) -> None:
        plain = self._xmp(b'<x:xmpmeta xmlns:x="adobe:ns:meta/"/>')
        assert not mpf.has_gcontainer(_with_segment(_PRIMARY, 0xE1, plain))

    def test_outside_xmp(self) -> None:
        assert not mpf.has_gcontainer(_with_segment(_PRIMARY, 0xFE, CONTAINER_XMP))
