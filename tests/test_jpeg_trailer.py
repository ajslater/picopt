"""Data appended after a JPEG's end of image survives optimization."""

import shutil
import struct
from collections.abc import Iterator, Sequence
from functools import cache
from io import BytesIO
from pathlib import Path

import mozjpeg_lossless_optimization
import pytest
from loguru import logger
from mozjpeg_lossless_optimization import COPY_MARKERS
from PIL import Image
from PIL.JpegImagePlugin import JpegImageFile
from PIL.MpoImagePlugin import MpoImageFile

from picopt import PROGRAM_NAME, cli
from picopt.config import PicoptConfig
from picopt.path import PathInfo
from picopt.pillow import jpeg_trailer
from picopt.plugins.jpeg import Jpeg, MozJpegTool
from tests import IMAGES_DIR, get_test_dir

__all__ = ()

TMP_ROOT = get_test_dir()

_XMP_ID = b"http://ns.adobe.com/xap/1.0/\x00"
_XMP_HEAD = (
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    b"<rdf:Description"
    b' xmlns:Container="http://ns.google.com/photos/1.0/container/"'
    b' xmlns:Item="http://ns.google.com/photos/1.0/container/item/"'
)
_XMP_TAIL = b"</rdf:Seq></Container:Directory></rdf:Description></rdf:RDF></x:xmpmeta>"
_PRIMARY_ITEM = (
    b'<rdf:li rdf:parseType="Resource">'
    b'<Container:Item Item:Semantic="Primary" Item:Mime="image/jpeg"/></rdf:li>'
)
# Pillow reads a JPEG with an APP1 containing ' hdrgm:Version="' as a JPEG,
# not an MPO, so an Ultra HDR photo goes to the JPEG handler.
_ULTRA_HDR_ATTRS = (
    b' xmlns:hdrgm="http://ns.adobe.com/hdr-gain-map/1.0/" hdrgm:Version="1.0">'
)
_MOTION_PHOTO_ATTRS = (
    b' xmlns:GCamera="http://ns.google.com/photos/1.0/camera/"'
    b' GCamera:MotionPhoto="1" GCamera:MotionPhotoVersion="1">'
)
# The start of an MP4: an ftyp box, then a free box.
_FTYP = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
_MP4 = _FTYP + b"\x00\x00\x01\x08free" + bytes(range(256))
# MP type codes in the low 24 bits of an MPEntry attribute.
_PRIMARY_ATTRIBUTE = 0x030000
_GAIN_MAP_ATTRIBUTE = 0x000000
# An offset in the primary's scan data, where no gain map can be.
_INSIDE_PRIMARY = 2000


def _segment(marker: int, payload: bytes) -> bytes:
    return struct.pack(">BBH", 0xFF, marker, len(payload) + 2) + payload


def _xmp(attrs: bytes, item: bytes) -> bytes:
    xmp = _XMP_HEAD + attrs + b"<Container:Directory><rdf:Seq>"
    xmp += _PRIMARY_ITEM + item + _XMP_TAIL
    return _segment(0xE1, _XMP_ID + xmp)


def _item(semantic: bytes, mime: bytes, length: int) -> bytes:
    return (
        b'<rdf:li rdf:parseType="Resource"><Container:Item'
        b' Item:Semantic="' + semantic + b'" Item:Mime="' + mime + b'"'
        b' Item:Length="' + str(length).encode() + b'"/></rdf:li>'
    )


def _jpeg(image: Image.Image, **kwargs) -> bytes:
    buf = BytesIO()
    image.save(buf, "JPEG", **kwargs)
    return buf.getvalue()


@cache
def _photo_image() -> Image.Image:
    with Image.open(IMAGES_DIR / "test_jpg.jpg") as image:
        return image.convert("RGB")


@cache
def _photo() -> bytes:
    """Return a photo mozjpeg can shrink."""
    return _jpeg(_photo_image(), quality=90)


@cache
def _gain_map() -> bytes:
    return _jpeg(Image.linear_gradient("L").resize((64, 48)))


def _mpf_segment(byte_order: str, entries: Sequence[tuple[int, int, int]]) -> bytes:
    """Return an APP2 MPF segment indexing ``(attribute, size, offset)`` entries."""
    header = b"II*\x00" if byte_order == "<" else b"MM\x00*"
    tag_count = 3
    ifd_offset = 8
    table_offset = ifd_offset + 2 + tag_count * 12 + 4
    ifd = struct.pack(byte_order + "H", tag_count)
    ifd += struct.pack(byte_order + "HHI4s", 0xB000, 7, 4, b"0100")
    ifd += struct.pack(byte_order + "HHII", 0xB001, 4, 1, len(entries))
    ifd += struct.pack(byte_order + "HHII", 0xB002, 7, 16 * len(entries), table_offset)
    ifd += struct.pack(byte_order + "I", 0)
    table = b"".join(
        struct.pack(byte_order + "IIIHH", attribute, size, offset, 0, 0)
        for attribute, size, offset in entries
    )
    payload = b"MPF\x00" + header + struct.pack(byte_order + "I", ifd_offset)
    return _segment(0xE2, payload + ifd + table)


def _ultra_hdr(*, byte_order: str = "<", gain_map_offset: int | None = None) -> bytes:
    """
    Build an Android Ultra HDR photo.

    The primary carries the gain map XMP and an MP Index, and the gain map
    JPEG follows its EOI. ``gain_map_offset`` overrides where the index says
    the gain map starts, counted from the start of the file.
    """
    photo, gain_map = _photo(), _gain_map()
    xmp = _xmp(_ULTRA_HDR_ATTRS, _item(b"GainMap", b"image/jpeg", len(gain_map)))
    mpf_len = len(_mpf_segment(byte_order, ((0, 0, 0),) * 2))
    primary_size = len(photo) + len(xmp) + mpf_len
    # SOI, the XMP, then the APP2 marker and length and "MPF\0".
    tiff_start = 2 + len(xmp) + 4 + 4
    if gain_map_offset is None:
        gain_map_offset = primary_size
    entries = (
        (_PRIMARY_ATTRIBUTE, primary_size, 0),
        (_GAIN_MAP_ATTRIBUTE, len(gain_map), gain_map_offset - tiff_start),
    )
    primary = photo[:2] + xmp + _mpf_segment(byte_order, entries) + photo[2:]
    return primary + gain_map


def _motion_photo() -> bytes:
    """Build a Google Motion Photo: a photo with an MP4 appended."""
    photo = _photo()
    xmp = _xmp(_MOTION_PHOTO_ATTRS, _item(b"MotionPhoto", b"video/mp4", len(_MP4)))
    return photo[:2] + xmp + photo[2:] + _MP4


def _frames(data: bytes) -> MpoImageFile:
    """Open every image the MP Index lists, as Pillow does for an MPO."""
    image = Image.open(BytesIO(data))
    assert image.format == "JPEG"
    assert isinstance(image, JpegImageFile)
    return MpoImageFile.adopt(image)


def _assert_gain_map_indexed(data: bytes) -> None:
    """Assert the MP Index finds the gain map, whole, after the primary."""
    end = jpeg_trailer.image_end(data)
    assert end is not None
    assert data[end:] == _gain_map()
    frames = _frames(data)
    assert frames.mpinfo is not None
    primary_entry, gain_map_entry = frames.mpinfo[0xB002]
    assert primary_entry["Size"] == end
    assert gain_map_entry["Size"] == len(_gain_map())
    frames.seek(1)
    with Image.open(BytesIO(_gain_map())) as gain_map:
        assert frames.tobytes() == gain_map.tobytes()


class TestImageEnd:
    """Find where the first image ends, as a decoder would."""

    def test_plain(self) -> None:
        photo = _photo()
        assert jpeg_trailer.image_end(photo) == len(photo)

    def test_appended_data(self) -> None:
        photo = _photo()
        assert jpeg_trailer.image_end(photo + _MP4) == len(photo)

    def test_eoi_in_segment_payload(self) -> None:
        # An EXIF thumbnail is a whole JPEG, EOI included, inside APP1.
        photo = _photo()
        exif = _segment(0xE1, b"Exif\x00\x00" + _gain_map())
        data = photo[:2] + exif + photo[2:]
        assert jpeg_trailer.image_end(data + _MP4) == len(data)

    @pytest.mark.parametrize(
        "kwargs",
        [{"progressive": True}, {"restart_marker_blocks": 1}],
        ids=["progressive", "restart_markers"],
    )
    def test_scans(self, kwargs: dict) -> None:
        data = _jpeg(_photo_image(), **kwargs)
        assert jpeg_trailer.image_end(data + _gain_map()) == len(data)

    def test_restart_markers_present(self) -> None:
        data = _jpeg(_photo_image(), restart_marker_blocks=1)
        assert b"\xff\xd0" in data

    def test_fill_bytes(self) -> None:
        data = _photo()[:-2] + b"\xff\xff\xff\xd9"
        assert jpeg_trailer.image_end(data + _MP4) == len(data)

    def test_garbage_before_marker(self) -> None:
        photo = _photo()
        data = photo[:2] + b"\x00\x00" + photo[2:]
        assert jpeg_trailer.image_end(data + _MP4) == len(data)

    @pytest.mark.parametrize(
        "data",
        [_photo()[:-2], _photo()[:1000], b"\x89PNG\r\n\x1a\n", b""],
        ids=["no_eoi", "truncated", "png", "empty"],
    )
    def test_none(self, data: bytes) -> None:
        assert jpeg_trailer.image_end(data) is None


class TestRejoin:
    """Put a recompressed image back in front of what followed it."""

    @staticmethod
    def _recompress(data: bytes) -> tuple[int, bytes]:
        end = jpeg_trailer.image_end(data)
        assert end is not None
        image = mozjpeg_lossless_optimization.optimize(
            data[:end], copy=COPY_MARKERS.ALL
        )
        return end, image

    def test_no_index(self) -> None:
        photo = _photo()
        assert jpeg_trailer.rejoin(photo + _MP4, len(photo), b"new") == b"new" + _MP4

    @pytest.mark.parametrize("byte_order", ["<", ">"])
    def test_ultra_hdr(self, byte_order: str) -> None:
        data = _ultra_hdr(byte_order=byte_order)
        _assert_gain_map_indexed(data)
        end, image = self._recompress(data)
        assert len(image) < end

        rejoined = jpeg_trailer.rejoin(data, end, image)

        assert rejoined.startswith(image[:2])
        _assert_gain_map_indexed(rejoined)

    def test_index_lost(self) -> None:
        data = _ultra_hdr()
        end, _ = self._recompress(data)
        with pytest.raises(jpeg_trailer.JpegTrailerError, match="lost its MP Index"):
            jpeg_trailer.rejoin(data, end, _photo())

    def test_image_outside_trailer(self) -> None:
        data = _ultra_hdr(gain_map_offset=_INSIDE_PRIMARY)
        end, image = self._recompress(data)
        with pytest.raises(jpeg_trailer.JpegTrailerError, match="image 2 of 2"):
            jpeg_trailer.rejoin(data, end, image)

    @pytest.mark.parametrize(
        ("payload", "match"),
        [
            (b"MPF\x00XX*\x00", "no TIFF header"),
            (b"MPF\x00II*\x00" + struct.pack("<I", 8), "truncated"),
            (
                b"MPF\x00II*\x00"
                + struct.pack("<IH", 8, 1)
                + struct.pack("<HHII", 0xB000, 7, 4, 0),
                "no MPEntry tag",
            ),
            (
                b"MPF\x00II*\x00"
                + struct.pack("<IH", 8, 1)
                + struct.pack("<HHII", 0xB002, 7, 15, 0),
                "MPEntry table is 15 bytes",
            ),
        ],
        ids=["no_tiff_header", "truncated", "no_mp_entry", "short_mp_entry"],
    )
    def test_malformed_index(self, payload: bytes, match: str) -> None:
        photo = _photo()
        data = photo[:2] + _segment(0xE2, payload) + photo[2:]
        with pytest.raises(jpeg_trailer.JpegTrailerError, match=match):
            jpeg_trailer.rejoin(data + _MP4, len(data), photo)


class TestOptimize:
    """A default run keeps appended data; the file still works."""

    @pytest.fixture(autouse=True)
    def _setup_and_teardown(self) -> Iterator[None]:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        TMP_ROOT.mkdir(parents=True)
        yield
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    @staticmethod
    def _run(name: str, data: bytes, *args: str) -> bytes:
        path = TMP_ROOT / name
        path.write_bytes(data)
        cli.main((PROGRAM_NAME, "-r", *args, str(TMP_ROOT)))
        return path.read_bytes()

    def test_ultra_hdr_keeps_gain_map(self) -> None:
        data = _ultra_hdr()
        optimized = self._run("PXL_ultra_hdr.jpg", data)
        assert len(optimized) < len(data)
        _assert_gain_map_indexed(optimized)

    def test_motion_photo_keeps_video(self) -> None:
        data = _motion_photo()
        optimized = self._run("PXL_motion.MP.jpg", data)
        assert len(optimized) < len(data)
        assert optimized.endswith(_MP4)
        assert jpeg_trailer.image_end(optimized) == len(optimized) - len(_MP4)

    def test_strip_metadata_drops_appended_data(self) -> None:
        # The XMP and MP Index that point to the appended data go too.
        optimized = self._run("PXL_motion.MP.jpg", _motion_photo(), "-M")
        assert jpeg_trailer.image_end(optimized) == len(optimized)
        assert b"http://ns.google.com/photos/1.0/container/" not in optimized

    def test_mismatched_index_left_unchanged(self) -> None:
        data = _ultra_hdr(gain_map_offset=_INSIDE_PRIMARY)
        assert self._run("PXL_ultra_hdr.jpg", data) == data


def test_mismatched_index_warns(tmp_path: Path) -> None:
    """The tool says why it left a file unchanged."""
    data = _ultra_hdr(gain_map_offset=_INSIDE_PRIMARY)
    path = tmp_path / "PXL_ultra_hdr.jpg"
    path.write_bytes(data)
    config = PicoptConfig().get_config(cli.get_arguments((PROGRAM_NAME, str(path))))
    path_info = PathInfo(top_path=tmp_path, path=path, convert=False)
    handler = Jpeg(
        config, path_info, input_file_format=Jpeg.OUTPUT_FILE_FORMAT, info={}
    )
    messages: list[str] = []
    sink = logger.add(messages.append, level="WARNING", format="{message}")
    try:
        output = MozJpegTool().run_stage(handler, BytesIO(data))
    finally:
        logger.remove(sink)
    assert output.getvalue() == data
    assert len(messages) == 1
    assert "image 2 of 2" in messages[0]
    assert "leaving it unchanged" in messages[0]
