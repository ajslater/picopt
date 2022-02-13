"""Test the unpack utility."""
from picopt.pillow.png_bit_depth import PNG_HEADER
from picopt.pillow.unpack import unpack
from tests import IMAGES_DIR


__all__ = ()  # hides module from pydocstring
TEST_SRC_PATH = IMAGES_DIR / "test_png.png"


def test_unpack_c() -> None:
    with open(TEST_SRC_PATH, "rb") as img:
        res = unpack("c", 8, img)
        assert res == PNG_HEADER
