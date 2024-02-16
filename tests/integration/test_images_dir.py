"""Test comic format."""
import platform
from types import MappingProxyType

from picopt import PROGRAM_NAME, cli
from tests import get_test_dir
from tests.integration.base_test_images import BaseTestImagesDir

__all__ = ()
FNS = {
    "07themecamplist.pdf": (93676, 93676, ("pdf", 93676), ("pdf", 93676)),
    "test_animated_gif.gif": (16383, 16358, ("png", 13389), ("webp", 11894)),
    "test_animated_png.png": (63435, 63435, ("png", 63435), ("webp", 53430)),
    "test_animated_webp.webp": (13610, 12178, ("webp", 12178), ("webp", 12178)),
    "test_png.png": (7967, 4149, ("png", 4149), ("webp", 3870)),
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
    "mri.tif": (230578, 230578, ("png", 131743), ("webp", 114740)),
    "test_webp_lossy.webp": (2764, 2764, ("webp", 2764), ("webp", 2764)),
    "test_bmp.bmp": (141430, 141430, ("png", 67236), ("webp", 47524)),
    "test_png_16rgba.png": (3435, 2090, ("png", 2090), ("webp", 1142)),
    "test_pnm.pnm": (27661, 27661, ("png", 15510), ("webp", 12808)),
    "test_jpg.jpg": (97373, 87913, ("jpg", 87913), ("jpg", 87913)),
}
if platform.system() == "Darwin":
    FNS.update(
        {
            "test_gif.gif": (138952, 138944, ("png", 112137), ("webp", 107924)),
            "test_pre-optimized_png.png": (
                256572,
                256572,
                ("png", 256572),
                ("webp", 197726),
            ),
            "eight.tif": (59640, 59640, ("png", 30585), ("webp", 24974)),
        }
    )
else:
    FNS.update(
        {
            "test_gif.gif": (138952, 138944, ("png", 112137), ("webp", 107952)),
            "test_pre-optimized_png.png": (
                256572,
                256572,
                ("png", 256572),
                ("webp", 197680),
            ),
            "eight.tif": (59640, 59640, ("png", 30585), ("webp", 24982)),
        }
    )

NEAR_LOSSLESS_FNS = MappingProxyType(
    {
        "test_png_16rgba.png": (3435, 2090, ("png", 2090), ("webp", 728)),
        "test_webp_lossless.webp": (5334, 3870, ("webp", 3870), ("webp", 2044)),
        "test_webp_lossless_pre-optimized.webp": (
            3798,
            3798,
            ("webp", 3798),
            ("webp", 3798),
        ),
    }
)


class TestImagesDir(BaseTestImagesDir):
    """Test images dir."""

    FNS = FNS
    TMP_ROOT = get_test_dir()

    def test_no_convert(self) -> None:
        """Test no convert."""
        args = (PROGRAM_NAME, "-rvvx SVG", str(self.TMP_ROOT))
        cli.main(args)
        for name, sizes in self.FNS.items():
            path = self.TMP_ROOT / name
            assert path.stat().st_size == sizes[1]

    def test_convert_to_png(self) -> None:
        """Test convert to PNG."""
        args = (
            PROGRAM_NAME,
            "-rvvx",
            "BMP,PPM,SVG,TIFF",
            "-c",
            "PNG",
            str(self.TMP_ROOT),
        )
        cli.main(args)
        for name, sizes in self.FNS.items():
            path = (self.TMP_ROOT / name).with_suffix("." + sizes[2][0])
            assert path.stat().st_size == sizes[2][1]

    def test_convert_to_webp(self) -> None:
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
        for name, sizes in self.FNS.items():
            path = (self.TMP_ROOT / name).with_suffix("." + sizes[3][0])
            assert path.stat().st_size == sizes[3][1]


class TestNearLosslessImageDir(BaseTestImagesDir):
    FNS = NEAR_LOSSLESS_FNS

    def test_convert_to_webp_near_lossless(self) -> None:
        """Test convert to WEBP."""
        args = (
            PROGRAM_NAME,
            "-rvvvnc",
            "WEBP",
            str(self.TMP_ROOT),
        )
        cli.main(args)
        for name, sizes in self.FNS.items():
            path = (self.TMP_ROOT / name).with_suffix("." + sizes[3][0])
            assert path.stat().st_size == sizes[3][1]
