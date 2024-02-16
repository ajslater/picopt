"""Test comic format."""
from types import MappingProxyType

from picopt import PROGRAM_NAME, cli
from tests import get_test_dir
from tests.integration.base_test_images import BaseTestImagesDir

__all__ = ()

FNS = MappingProxyType(
    {
        "test_pre-optimized_jpg.jpg": (
            22664,
            22664,
            ("jpg", 22664),
            ("jpg", 22664),
        ),
        "test_mpo.jpeg": (
            7106225,
            7106225,
            ("jpeg", 5963686),
            ("jpeg", 6450372),
        ),
    }
)


class TestMPO(BaseTestImagesDir):
    """Test images dir."""

    TMP_ROOT = get_test_dir()
    FNS = FNS

    def test_no_convert(self) -> None:
        """Test no convert."""
        args = (PROGRAM_NAME, "-rvvv", str(self.TMP_ROOT))
        cli.main(args)
        for name, sizes in self.FNS.items():
            path = self.TMP_ROOT / name
            assert path.stat().st_size == sizes[1]

    def test_convert_to_jpeg(self) -> None:
        """Test convert to PNG."""
        args = (PROGRAM_NAME, "-rvvvx", "MPO", "-c", "JPEG", str(self.TMP_ROOT))
        cli.main(args)
        for name, sizes in self.FNS.items():
            path = (self.TMP_ROOT / name).with_suffix("." + sizes[2][0])
            assert path.stat().st_size == sizes[2][1]

    def test_convert_to_jpeg_no_local(self) -> None:
        """Test convert to PNG."""
        args = (
            PROGRAM_NAME,
            "-rvvvx",
            "MPO",
            "-c",
            "JPEG",
            "-D",
            "mozjpeg,jpegtran",
            str(self.TMP_ROOT),
        )
        cli.main(args)
        for name, sizes in self.FNS.items():
            path = (self.TMP_ROOT / name).with_suffix("." + sizes[3][0])
            assert path.stat().st_size == sizes[3][1]
