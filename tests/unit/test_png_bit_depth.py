"""Test png bit depth utility module."""
import sys

from picopt.pillow.png_bit_depth import main, png_bit_depth
from tests import IMAGES_DIR

__all__ = ()  # hides module from pydocstring
TEST_SRC_PATH = IMAGES_DIR / "test_png.png"
TEST_SRC_PATH_16 = IMAGES_DIR / "test_png_16rgba.png"
TEST_SRC_PATH_JPG = IMAGES_DIR / "test_jpg.jpg"


def test_png_bit_depth() -> None:
    """Test PNG bit depth."""
    with TEST_SRC_PATH.open("rb") as png_file:
        res = png_bit_depth(png_file)
    assert res == 8  # noqa PLR2004


def test_png_bit_depth_16() -> None:
    """Test PNG bit depth 16."""
    with TEST_SRC_PATH_16.open("rb") as png_file:
        res = png_bit_depth(png_file)
    assert res == 16  # noqa PLR2004


def test_png_bit_depth_invalid() -> None:
    """Test PNG bit depth invalid."""
    with TEST_SRC_PATH_JPG.open("rb") as jpg_file:
        res = png_bit_depth(jpg_file)
    assert res is None


def test_main() -> None:
    """Test main."""
    sys.argv[1] = str(TEST_SRC_PATH)
    main()
