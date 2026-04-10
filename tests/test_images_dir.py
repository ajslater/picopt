"""Test comic format."""

from pathlib import Path
from types import MappingProxyType

import pytest

from picopt import PROGRAM_NAME, cli
from tests import IMAGES_DIR, assert_size_close, get_test_dir
from tests.base import BaseTest

__all__ = ()
# Output sizes are targets, not exact expectations: see assert_size_close in
# tests/__init__.py. Where the linux and darwin builds historically reported
# different sizes, the value below is the midpoint so each platform stays well
# within tolerance.
FNS = MappingProxyType(
    {
        # orig, no convert, convert, webp
        "07themecamplist.pdf": (93676, 93676, ("pdf", 93676), ("pdf", 93676)),
        "test_animated_webp.webp": (11856, 11856, ("webp", 11856), ("webp", 11856)),
        "test_png.png": (7967, 4150, ("png", 4150), ("webp", 3870)),
        "test_pre-optimized_jpg.jpg": (
            22664,
            22664,
            ("jpg", 22664),
            ("jpg", 22664),
        ),
        "test_svg.svg": (5393, 4871, ("svg", 4871), ("svg", 4871)),
        "test_txt.txt": (6, 6, ("txt", 6), ("txt", 6)),
        "test_webp_lossless.webp": (5334, 3870, ("webp", 3870), ("webp", 3870)),
        "test_webp_lossy.webp": (2764, 2764, ("webp", 2764), ("webp", 2764)),
        "test_png_16rgba.png": (3435, 2097, ("png", 2097), ("webp", 1142)),
        "test_jpg.jpg": (97373, 87913, ("jpg", 87913), ("jpg", 87913)),
        "test_animated_gif.gif": (16383, 16358, ("png", 16012), ("webp", 11856)),
        "test_animated_png.png": (63435, 61372, ("png", 61372), ("webp", 52972)),
        "test_pre-optimized_png.png": (
            256572,
            256572,
            ("png", 256572),
            ("webp", 197086),
        ),
        "test_webp_lossless_pre-optimized.webp": (
            3794,
            3794,
            ("webp", 3796),
            ("webp", 3794),
        ),
        "eight.tif": (59640, 59640, ("png", 30585), ("webp", 25000)),
        "mri.tif": (230578, 230578, ("png", 128982), ("webp", 115832)),
        "test_bmp.bmp": (141430, 141430, ("png", 67236), ("webp", 47410)),
        "test_pnm.pnm": (27661, 27661, ("png", 15510), ("webp", 12743)),
        "test_gif.gif": (138952, 138944, ("png", 112290), ("webp", 108015)),
    }
)

NEAR_LOSSLESS_FNS = MappingProxyType(
    {
        "test_png_16rgba.png": (3435, 2097, ("png", 2097), ("webp", 728)),
        "test_webp_lossless.webp": (5334, 3870, ("webp", 3870), ("webp", 2044)),
        "test_webp_lossless_pre-optimized.webp": (
            3794,
            3794,
            ("webp", 3794),
            ("webp", 3794),
        ),
    }
)


@pytest.mark.parametrize("fn", FNS)
class TestImagesDir(BaseTest):
    """Test images dir."""

    TMP_ROOT: Path = get_test_dir()
    SOURCE_DIR: Path = IMAGES_DIR
    FNS: MappingProxyType[str, tuple] = FNS

    def test_no_convert(self, fn: str) -> None:
        """Test no convert."""
        args = (PROGRAM_NAME, "-rvvx SVG", str(self.TMP_ROOT))
        cli.main(args)
        path = self.TMP_ROOT / fn
        size = FNS[fn][1]
        assert_size_close(path.stat().st_size, size)

    def test_convert_to_png(self, fn: str) -> None:
        """Test convert to PNG."""
        args = (
            PROGRAM_NAME,
            "-rvvbx",
            "BMP,PPM,SVG,TIFF",
            "-c",
            "PNG",
            str(self.TMP_ROOT),
        )
        cli.main(args)
        suffix, size = FNS[fn][2]
        path = (self.TMP_ROOT / fn).with_suffix("." + suffix)
        assert_size_close(path.stat().st_size, size)

    def test_convert_to_webp(self, fn: str) -> None:
        """Test convert to WEBP."""
        args = (
            PROGRAM_NAME,
            "-rvvx",
            "BMP,PPM,SVG,TIFF",
            "-c",
            "WEBP",
            str(self.TMP_ROOT),
        )
        cli.main(args)
        suffix, size = FNS[fn][3]
        path = (self.TMP_ROOT / fn).with_suffix("." + suffix)
        assert_size_close(path.stat().st_size, size)


@pytest.mark.parametrize("fn", NEAR_LOSSLESS_FNS)
class TestNearLosslessImageDir(BaseTest):
    TMP_ROOT: Path = get_test_dir()
    SOURCE_DIR: Path = IMAGES_DIR
    FNS: MappingProxyType[str, tuple] = NEAR_LOSSLESS_FNS

    def test_convert_to_webp_near_lossless(self, fn: str) -> None:
        """Test convert to WEBP."""
        args = (
            PROGRAM_NAME,
            "-rvvvnc",
            "WEBP",
            str(self.TMP_ROOT),
        )
        cli.main(args)
        suffix, size = self.FNS[fn][3]
        path = (self.TMP_ROOT / fn).with_suffix("." + suffix)
        assert_size_close(path.stat().st_size, size)
