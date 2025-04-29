"""Test comic format."""

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
        ),
        "test_jpg.jpg": (
            97373,
            87913,
        ),
    }
)
STATS = ("uid", "gid", "mode", "mtime_ns")


@pytest.mark.parametrize("fn", FNS)
class TestPreserve(BaseTest):
    """Test images dir."""

    TMP_ROOT = get_test_dir()
    SOURCE_DIR = IMAGES_DIR
    FNS = FNS

    def test_preserve(self, fn: str) -> None:
        """Test no convert."""
        path = self.TMP_ROOT / fn
        old_stat = path.stat()
        args = (PROGRAM_NAME, "-rpvvv", str(self.TMP_ROOT))
        cli.main(args)
        new_stat = path.stat()
        size = FNS[fn][1]
        assert new_stat.st_size == size
        for stat_name_suffix in STATS:
            stat_name = "st_" + stat_name_suffix
            assert getattr(old_stat, stat_name) == getattr(new_stat, stat_name)
