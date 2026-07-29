"""Test the JXL codestream sniffer."""

import io
from pathlib import Path

import pytest
from PIL import Image

# Importing this registers the JXL codec with Pillow, which the encodes below
# rely on.
from picopt.pillow.jxl import is_lossless
from tests import IMAGES_DIR

__all__ = ()

_CONTAINER_SIG = b"\x00\x00\x00\x0cJXL \x0d\x0a\x87\x0a"
_SRC = IMAGES_DIR / "test_png.png"
_JPEG_SRC = IMAGES_DIR / "test_jpg.jpg"


def _encode(src: Path, mode: str | None = None, **kwargs) -> bytes:
    with Image.open(src) as opened:
        image = opened.convert(mode) if mode else opened
        buf = io.BytesIO()
        image.save(buf, "JXL", effort=7, **kwargs)
        return buf.getvalue()


def test_codec_is_registered() -> None:
    """
    Importing the module must register the codec, read and write.

    The import exists only for that side effect, which makes it look unused;
    autofixers have removed it before.
    """
    assert "JXL" in Image.OPEN
    assert "JXL" in Image.SAVE
    # picopt's pil_save always passes save_all=True, which raises KeyError
    # for formats missing from this registry.
    assert "JXL" in Image.SAVE_ALL


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L"])
def test_lossless_encodes_are_lossless(mode: str) -> None:
    """A lossless encode is detected in both container and bare form."""
    for use_container in (False, True):
        data = _encode(_SRC, mode, lossless=True, use_container=use_container)
        assert (data[:12] == _CONTAINER_SIG) is use_container
        assert is_lossless(io.BytesIO(data))


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L"])
def test_lossy_encodes_are_not_lossless(mode: str) -> None:
    """An XYB encoded file is never offered for re-encoding."""
    for use_container in (False, True):
        data = _encode(
            _SRC, mode, lossless=False, quality=90, use_container=use_container
        )
        assert not is_lossless(io.BytesIO(data))


def test_sixteen_bit_lossless() -> None:
    """16 bit samples parse past the extra channel info."""
    data = _encode(IMAGES_DIR / "test_png_16rgba.png", lossless=True)
    assert is_lossless(io.BytesIO(data))


def test_jpeg_reconstruction_is_not_reencodable() -> None:
    """Re-encoding would drop the jbrd box, so it must report False."""
    data = _encode(_JPEG_SRC, lossless_jpeg=True, lossless=True)
    assert not is_lossless(io.BytesIO(data))


def test_fixtures() -> None:
    """The committed fixtures: one lossless, one lossy."""
    assert is_lossless(io.BytesIO((IMAGES_DIR / "test_jxl_lossless.jxl").read_bytes()))
    assert not is_lossless(io.BytesIO((IMAGES_DIR / "test_jxl_lossy.jxl").read_bytes()))


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\xff\x0a",
        b"\xff\x0a\x01",
        _CONTAINER_SIG,
        _CONTAINER_SIG + b"\x00\x00",
        # A box header claiming a size smaller than the header itself.
        _CONTAINER_SIG + b"\x00\x00\x00\x02jxlc",
        b"\x89PNG\r\n\x1a\n" + bytes(40),
        bytes(64),
    ],
)
def test_junk_is_never_lossless(data: bytes) -> None:
    """Truncated or foreign input must be refused, not crash."""
    assert not is_lossless(io.BytesIO(data))


def test_buffer_is_rewound() -> None:
    """The caller's buffer position is restored, like the webp sniffer."""
    data = _encode(_SRC, "RGB", lossless=True)
    buf = io.BytesIO(data)
    is_lossless(buf)
    assert buf.tell() == 0
