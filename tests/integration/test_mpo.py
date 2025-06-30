"""Test comic format."""

from pathlib import Path
from types import MappingProxyType

import pytest

from picopt import PROGRAM_NAME, cli
from tests import IMAGES_DIR, get_test_dir
from tests.integration.base import BaseTest

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
            ("jpeg", 5963704),
            ("jpeg", 6450372),
        ),
    }
)


@pytest.mark.parametrize("fn", FNS)
class TestMPO(BaseTest):
    """Test images dir."""

    TMP_ROOT: Path = get_test_dir()
    SOURCE_DIR: Path = IMAGES_DIR
    FNS: MappingProxyType[str, tuple] = FNS

    def test_no_convert(self, fn: str) -> None:
        """Test no convert."""
        args = (PROGRAM_NAME, "-rvvv", str(self.TMP_ROOT))
        cli.main(args)
        path = self.TMP_ROOT / fn
        size = FNS[fn][1]
        assert path.stat().st_size == size

    def test_convert_to_jpeg(self, fn: str) -> None:
        """Test convert to PNG."""
        args = (PROGRAM_NAME, "-rvvvx", "MPO", "-c", "JPEG", str(self.TMP_ROOT))
        cli.main(args)
        suffix, size = FNS[fn][2]
        path = (self.TMP_ROOT / fn).with_suffix("." + suffix)
        assert path.stat().st_size == size

    def test_convert_to_jpeg_disable_internal_mozjpeg(self, fn: str) -> None:
        """Test convert to Jpeg from MPO."""
        args = (
            PROGRAM_NAME,
            "-rvvvx",
            "MPO",
            "-c",
            "JPEG",
            "-D",
            "internal_mozjpeg",
            str(self.TMP_ROOT),
        )
        cli.main(args)
        suffix, size = FNS[fn][3]
        path = (self.TMP_ROOT / fn).with_suffix("." + suffix)
        assert path.stat().st_size == size
