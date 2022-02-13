"""Test png bit depth utility module."""
import sys

from picopt.pillow.webp_lossless import is_lossless, main
from tests import IMAGES_DIR


__all__ = ()  # hides module from pydocstring
TEST_SRC_LOSSLESS_PATH = str(IMAGES_DIR / "test_webp_lossless.webp")
TEST_SRC_LOSSY_PATH = str(IMAGES_DIR / "test_webp_lossy.webp")
TEST_SRC_ANIMATED_PATH = str(IMAGES_DIR / "test_animated_webp.webp")
TEST_SRC_JPEG_PATH = str(IMAGES_DIR / "test_jpg.jpg")


def test_is_lossless_webp_lossless() -> None:
    res = is_lossless(TEST_SRC_LOSSLESS_PATH)
    assert res


def test_is_lossless_webp_lossy() -> None:
    res = is_lossless(TEST_SRC_LOSSY_PATH)
    assert res is False


def test_is_lossless_animated_webp() -> None:
    res = is_lossless(TEST_SRC_ANIMATED_PATH)
    assert res is False


def test_is_lossless_jpeg() -> None:
    res = is_lossless(TEST_SRC_JPEG_PATH)
    assert res is False


def test_webp_is_lossless_main() -> None:
    sys.argv[1] = str(TEST_SRC_LOSSLESS_PATH)
    main()
