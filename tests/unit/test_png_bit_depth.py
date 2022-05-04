"""Test png bit depth utility module."""
import sys

from picopt.pillow.png_bit_depth import main, png_bit_depth
from tests import IMAGES_DIR


__all__ = ()  # hides module from pydocstring
TEST_SRC_PATH = IMAGES_DIR / "test_png.png"
TEST_SRC_PATH_16 = IMAGES_DIR / "test_png_16rgba.png"
TEST_SRC_PATH_JPG = IMAGES_DIR / "test_jpg.jpg"


def test_png_bit_depth() -> None:
    res = png_bit_depth(TEST_SRC_PATH)
    assert res == 8


def test_png_bit_depth_16() -> None:
    res = png_bit_depth(TEST_SRC_PATH_16)
    assert res == 16


def test_png_bit_depth_invalid() -> None:
    res = png_bit_depth(TEST_SRC_PATH_JPG)
    assert res is None


def test_main() -> None:
    sys.argv[1] = str(TEST_SRC_PATH)
    main()
