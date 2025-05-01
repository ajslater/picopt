"""Test comic format."""

import platform
from types import MappingProxyType

import pytest

from picopt import PROGRAM_NAME, cli
from tests import IMAGES_DIR, get_test_dir
from tests.integration.base import BaseTest

__all__ = ()
FNS = {
    "07themecamplist.pdf": (93676, 93676, ("pdf", 93676), ("pdf", 93676)),
    "test_animated_gif.gif": (16383, 16358, ("png", 24255), ("webp", 11892)),
    "test_animated_webp.webp": (13610, 12174, ("webp", 12174), ("webp", 12174)),
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
    "test_webp_lossless_pre-optimized.webp": (
        3798,
        3798,
        ("webp", 3798),
        ("webp", 3798),
    ),
    "mri.tif": (230578, 230578, ("png", 129479), ("webp", 116954)),
    "test_webp_lossy.webp": (2764, 2764, ("webp", 2764), ("webp", 2764)),
    "test_png_16rgba.png": (3435, 2097, ("png", 2097), ("webp", 1142)),
    "test_jpg.jpg": (97373, 87913, ("jpg", 87913), ("jpg", 87913)),
}
if platform.system() == "Darwin":
    FNS.update(
        {
            "test_animated_png.png": (63435, 63058, ("png", 63058), ("webp", 52864)),
            "test_gif.gif": (138952, 138944, ("png", 112290), ("webp", 108058)),
            "test_pre-optimized_png.png": (
                256572,
                256572,
                ("png", 256572),
                ("webp", 197088),
            ),
            "eight.tif": (59640, 59640, ("png", 30585), ("webp", 25012)),
            "test_bmp.bmp": (141430, 141430, ("png", 67236), ("webp", 47436)),
            "test_pnm.pnm": (27661, 27661, ("png", 15510), ("webp", 12758)),
        }
    )
else:
    FNS.update(
        {
            "test_animated_png.png": (63435, 63058, ("png", 63058), ("webp", 52864)),
            "test_gif.gif": (138952, 138944, ("png", 112290), ("webp", 107924)),
            "test_pre-optimized_png.png": (
                256572,
                256572,
                ("png", 256572),
                ("webp", 197726),
            ),
            "eight.tif": (59640, 59640, ("png", 30585), ("webp", 24974)),
            "test_bmp.bmp": (141430, 141430, ("png", 67236), ("webp", 47524)),
            "test_pnm.pnm": (27661, 27661, ("png", 15510), ("webp", 12808)),
        }
    )

NEAR_LOSSLESS_FNS = MappingProxyType(
    {
        "test_png_16rgba.png": (3435, 2097, ("png", 2097), ("webp", 728)),
        "test_webp_lossless.webp": (5334, 3870, ("webp", 3870), ("webp", 2044)),
        "test_webp_lossless_pre-optimized.webp": (
            3798,
            3798,
            ("webp", 3798),
            ("webp", 3798),
        ),
    }
)


@pytest.mark.parametrize("fn", FNS)
class TestImagesDir(BaseTest):
    """Test images dir."""

    TMP_ROOT = get_test_dir()
    SOURCE_DIR = IMAGES_DIR
    FNS = FNS

    def test_no_convert(self, fn: str) -> None:
        """Test no convert."""
        args = (PROGRAM_NAME, "-rvvx SVG", str(self.TMP_ROOT))
        cli.main(args)
        path = self.TMP_ROOT / fn
        size = FNS[fn][1]
        assert path.stat().st_size == size

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
        assert path.stat().st_size == size

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
        assert path.stat().st_size == size


@pytest.mark.parametrize("fn", NEAR_LOSSLESS_FNS)
class TestNearLosslessImageDir(BaseTest):
    TMP_ROOT = get_test_dir()
    SOURCE_DIR = IMAGES_DIR
    FNS = NEAR_LOSSLESS_FNS

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
        assert path.stat().st_size == size
