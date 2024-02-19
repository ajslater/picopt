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
        ),
        "test_jpg.jpg": (
            97373,
            87913,
            ("jpg", 87913),
        ),
    }
)
STATS = ("uid", "gid", "mode", "mtime_ns")


class TestPreserve(BaseTestImagesDir):
    """Test images dir."""

    TMP_ROOT = get_test_dir()
    FNS = FNS

    def test_preserve(self) -> None:
        """Test no convert."""
        stats = {}
        for name in self.FNS:
            path = self.TMP_ROOT / name
            stats[path] = path.stat()
        args = (PROGRAM_NAME, "-rpvvv", str(self.TMP_ROOT))
        cli.main(args)
        for name, sizes in self.FNS.items():
            path = self.TMP_ROOT / name
            old_stat = stats[path]
            new_stat = path.stat()
            assert new_stat.st_size == sizes[1]
            print(name)
            for stat_name_suffix in STATS:
                stat_name = "st_" + stat_name_suffix
                print(f"\t{stat_name}")
                assert getattr(old_stat, stat_name) == getattr(new_stat, stat_name)
