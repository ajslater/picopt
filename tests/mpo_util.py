"""Build MPO fixtures for the MPO tests."""

import struct
from collections.abc import Sequence
from io import BytesIO

from PIL import ExifTags, Image, ImageCms

from picopt.pillow import mpf
from tests import IMAGES_DIR

__all__ = (
    "CAMERA_MPO",
    "CONTAINER_XMP",
    "build_mpo",
    "jpeg",
    "make_mpo",
    "xmp_segment_count",
)

# A camera MPO: the primary image and a Full HD thumbnail.
CAMERA_MPO = IMAGES_DIR / "test_mpo.jpeg"

_PLAIN_XMP = b'<x:xmpmeta xmlns:x="adobe:ns:meta/"/>'
# The GContainer namespace under the prefix Ultra HDR and Motion Photo use.
CONTAINER_XMP = (
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    b'<rdf:Description xmlns:Container="http://ns.google.com/photos/1.0/container/"/>'
    b"</rdf:RDF></x:xmpmeta>"
)
_XMP_ID = b"http://ns.adobe.com/xap/1.0/\x00"
_APP1 = 0xE1
# MP type codes in the low 24 bits of an MPEntry attribute.
_PRIMARY_ATTRIBUTE = 0x030000
_UNDEFINED_ATTRIBUTE = 0x000000
# SOI, then the APP2 marker and length, then "MPF\0".
_TIFF_START = 2 + 4 + 4


def make_mpo(*, xmp: bytes = _PLAIN_XMP) -> bytes:
    """
    Build an iPhone-style MPO with Pillow: a photo and a grayscale gain map.

    The photo carries EXIF, XMP and an ICC profile. Pillow writes a
    little-endian index typed "Baseline MP Primary Image" + "Undefined".
    """
    with Image.open(IMAGES_DIR / "test_jpg.jpg") as source:
        photo = source.convert("RGB")
    gain_map = photo.convert("L").reduce(2)
    exif = Image.Exif()
    exif[ExifTags.Base.Artist] = "picopt-test"
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    buf = BytesIO()
    photo.save(
        buf,
        "MPO",
        save_all=True,
        append_images=[gain_map],
        exif=exif.tobytes(),
        xmp=xmp,
        icc_profile=icc,
    )
    return buf.getvalue()


def jpeg(size: tuple[int, int], color: tuple[int, int, int]) -> bytes:
    """Return a small plain JPEG."""
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return buf.getvalue()


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
    payload += ifd + table
    return b"\xff\xe2" + struct.pack(">H", len(payload) + 2) + payload


def build_mpo(
    images: Sequence[bytes],
    *,
    byte_order: str = "<",
    gap: bytes = b"",
    trailer: bytes = b"",
) -> bytes:
    """Index ``images`` in an MPF segment placed right after the first's SOI."""
    segment_len = len(_mpf_segment(byte_order, [(0, 0, 0)] * len(images)))
    primary_size = len(images[0]) + segment_len
    entries = [(_PRIMARY_ATTRIBUTE, primary_size, 0)]
    pos = primary_size
    for image in images[1:]:
        pos += len(gap)
        entries.append((_UNDEFINED_ATTRIBUTE, len(image), pos - _TIFF_START))
        pos += len(image)
    primary = images[0][:2] + _mpf_segment(byte_order, entries) + images[0][2:]
    return primary + b"".join(gap + image for image in images[1:]) + trailer


def xmp_segment_count(data: bytes) -> int:
    """Count the XMP APP1 segments in the first image."""
    return sum(
        marker == _APP1 and data.startswith(_XMP_ID, start + 4)
        for marker, start, _ in mpf.iter_segments(data)
    )
