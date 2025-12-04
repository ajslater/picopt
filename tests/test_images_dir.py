"""Test comic format."""

import platform
from pathlib import Path
from types import MappingProxyType

import pytest

from picopt import PROGRAM_NAME, cli
from tests import IMAGES_DIR, get_test_dir
from tests.base import BaseTest

__all__ = ()
FNS = {
    # orig, no convert, convert, webp
    "07themecamplist.pdf": (
        93676,
        93676,
        ("pdf", 93676),
        ("pdf", 93676),
        ("pdf", 93676),
    ),
    "test_animated_webp.webp": (
        11856,
        11856,
        ("webp", 11856),
        ("webp", 11856),
        ("webp", 11856),
    ),
    "test_png.png": (7967, 4150, ("png", 4150), ("webp", 3870), ("jxl", 3971)),
    "test_pre-optimized_jpg.jpg": (
        22664,
        22664,
        ("jpg", 22664),
        ("jpg", 22664),
        ("jxl", 20711),
    ),
    "test_svg.svg": (5393, 4871, ("svg", 4871), ("svg", 4871), ("svg", 4871)),
    "test_txt.txt": (6, 6, ("txt", 6), ("txt", 6), ("txt", 6)),
    "test_webp_lossless.webp": (
        5334,
        3870,
        ("webp", 3870),
        ("webp", 3870),
        # BUG NOT FOUND
        ("jxl", 3870),
    ),
    "test_webp_lossy.webp": (
        2764,
        2764,
        ("webp", 2764),
        ("webp", 2764),
        ("webp", 2764),
    ),
    "test_png_16rgba.png": (3435, 2097, ("png", 2097), ("webp", 1142), ("jxl", 1053)),
    "test_jpg.jpg": (97373, 87913, ("jpg", 87913), ("jpg", 87913), ("jxl", 16237)),
    # BUG jxl convert on 2 & 4 gets too big
    "test_jxl.jxl": (77911, 77911, ("jxl", 94618), ("jxl", 77911), ("jxl", 94618)),
}
if platform.system() == "Darwin":
    FNS.update(
        {
            "test_animated_gif.gif": (
                16383,
                16358,
                ("png", 16582),
                ("webp", 11856),
                # BUG not found
                ("jxl", 3438),
            ),
            "test_animated_png.png": (
                63435,
                61393,
                ("png", 61393),
                ("webp", 52972),
                # BUG not found
                ("jxl", 3402),
            ),
            "test_pre-optimized_png.png": (
                256572,
                256572,
                ("png", 256572),
                ("webp", 197084),
                # BUG not found
                ("jxl", 114836),
            ),
            "test_webp_lossless_pre-optimized.webp": (
                3794,
                3794,
                ("webp", 3794),
                ("webp", 3794),
                # BUG not found
                ("jxl", 4172),
            ),
            "eight.tif": (
                59640,
                59640,
                ("png", 30585),
                ("webp", 24988),
                ("jxl", 21996),
            ),
            "mri.tif": (
                230578,
                230578,
                ("png", 129479),
                ("webp", 114710),
                ("jxl", 4182),
            ),
            "test_bmp.bmp": (
                141430,
                141430,
                ("png", 67236),
                ("webp", 47384),
                ("jxl", 41218),
            ),
            "test_pnm.pnm": (
                27661,
                27661,
                ("png", 15510),
                ("webp", 12728),
                ("jxl", 12107),
            ),
            "test_gif.gif": (
                138952,
                138944,
                ("png", 112290),
                ("webp", 107972),
                ("jxl", 114836),
            ),
        }
    )
else:
    FNS.update(
        {
            "test_animated_gif.gif": (
                16383,
                16358,
                ("png", 16582),
                ("webp", 11856),
                ("jxl", 3438),
            ),
            "test_animated_png.png": (
                63435,
                61393,
                ("png", 61393),
                ("webp", 52972),
                ("jxl", 3402),
            ),
            "test_pre-optimized_png.png": (
                256572,
                256572,
                ("png", 256572),
                ("webp", 197088),
                ("jxl", 186092),
            ),
            "test_webp_lossless_pre-optimized.webp": (
                3794,
                3794,
                ("webp", 3798),
                ("webp", 3794),
                ("jxl", 4172),
            ),
            "eight.tif": (
                59640,
                59640,
                ("png", 30585),
                ("webp", 25012),
                ("jxl", 21996),
            ),
            "mri.tif": (
                230578,
                230578,
                ("png", 129479),
                ("webp", 116954),
                ("jxl", 4182),
            ),
            "test_bmp.bmp": (
                141430,
                141430,
                ("png", 67236),
                ("webp", 47436),
                ("jxl", 41218),
            ),
            "test_pnm.pnm": (
                27661,
                27661,
                ("png", 15510),
                ("webp", 12758),
                ("jxl", 12107),
            ),
            "test_gif.gif": (
                138952,
                138944,
                ("png", 112290),
                ("webp", 108058),
                ("jxl", 114836),
            ),
        }
    )

NEAR_LOSSLESS_FNS = MappingProxyType(
    {
        "test_png_16rgba.png": (
            3435,
            2097,
            ("png", 2097),
            ("webp", 728),
            ("jxl", 1053),
        ),
        "test_webp_lossless.webp": (
            5334,
            3870,
            ("webp", 3870),
            ("webp", 2044),
            ("jxl", 3934),
        ),
        "test_webp_lossless_pre-optimized.webp": (
            3794,
            3794,
            ("webp", 3794),
            ("webp", 3794),
            ("jxl", 4172),
        ),
    }
)


@pytest.mark.parametrize("fn", FNS)
class TestImagesDir(BaseTest):
    """Test images dir."""

    TMP_ROOT: Path = get_test_dir()
    SOURCE_DIR: Path = IMAGES_DIR
    FNS: MappingProxyType[str, tuple] = MappingProxyType(FNS)

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

    def test_convert_to_jxl(self, fn: str) -> None:
        args = (
            PROGRAM_NAME,
            "-rvvbx",
            "BMP,PPM,SVG,TIFF",
            "-c",
            "JXL",
            str(self.TMP_ROOT),
        )
        cli.main(args)
        suffix, size = FNS[fn][4]
        path = (self.TMP_ROOT / fn).with_suffix("." + suffix)
        assert path.stat().st_size == size


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
        assert path.stat().st_size == size

    def test_convert_to_jpegxl_near_lossless(self, fn: str) -> None:
        """Test convert to JPEGXL."""
        args = (
            PROGRAM_NAME,
            "-rvvvbnc",
            "JXL",
            str(self.TMP_ROOT),
        )
        cli.main(args)
        suffix, size = self.FNS[fn][4]
        path = (self.TMP_ROOT / fn).with_suffix("." + suffix)
        assert path.stat().st_size == size
