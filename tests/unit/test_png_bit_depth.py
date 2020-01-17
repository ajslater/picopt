"""Test png bit depth utility module."""
import sys

from picopt.formats import png_bit_depth
from tests import IMAGES_DIR


__all__ = ()  # hides module from pydocstring
TEST_SRC_PATH = IMAGES_DIR / "test_png.png"
TEST_SRC_PATH_16 = IMAGES_DIR / "test_png_16rgba.png"
TEST_SRC_PATH_JPG = IMAGES_DIR / "test_jpg.jpg"


def test_unpack_c() -> None:
    with open(TEST_SRC_PATH, "rb") as img:
        res = png_bit_depth.unpack("c", 8, img)
    assert res == png_bit_depth.PNG_HEADER


def test_png_bit_depth() -> None:
    res = png_bit_depth.png_bit_depth(TEST_SRC_PATH)
    assert res == 8


def test_png_bit_depth_16() -> None:
    res = png_bit_depth.png_bit_depth(TEST_SRC_PATH_16)
    assert res == 16


def test_png_bit_depth_invalid() -> None:
    res = png_bit_depth.png_bit_depth(TEST_SRC_PATH_JPG)
    assert res is None


def test_main() -> None:
    sys.argv[1] = str(TEST_SRC_PATH)
    png_bit_depth.main()
