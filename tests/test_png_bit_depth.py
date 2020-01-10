"""Test png bit depth utility module."""
import sys

from pathlib import Path

from picopt.formats import png_bit_depth


__all__ = ()  # hides module from pydocstring
TEST_FILES_ROOT = Path("tests/test_files")
IMAGES_ROOT = TEST_FILES_ROOT / "images"
TEST_SRC_PATH = IMAGES_ROOT / "test_png.png"
TEST_SRC_PATH_16 = IMAGES_ROOT / "test_png_16rgba.png"
TEST_SRC_PATH_JPG = IMAGES_ROOT / "test_jpg.jpg"


def test_unpack_c():
    with open(TEST_SRC_PATH, "rb") as img:
        res = png_bit_depth.unpack("c", 8, img)
    assert res == png_bit_depth.PNG_HEADER


def test_png_bit_depth():
    res = png_bit_depth.png_bit_depth(TEST_SRC_PATH)
    assert res == 8


def test_png_bit_depth_16():
    res = png_bit_depth.png_bit_depth(TEST_SRC_PATH_16)
    assert res == 16


def test_png_bit_depth_invalid():
    res = png_bit_depth.png_bit_depth(TEST_SRC_PATH_JPG)
    assert res is None


def test_main():
    sys.argv[1] = str(TEST_SRC_PATH)
    png_bit_depth.main()
