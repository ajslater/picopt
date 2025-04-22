"""Base class for testing images."""

import shutil
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

import pytest

from tests import IMAGES_DIR, get_test_dir


class BaseTest:
    """Test images dir."""

    TMP_ROOT: Path = get_test_dir()
    SOURCE_DIR: Path = IMAGES_DIR
    FNS: Mapping = MappingProxyType({})

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, fn: str):
        """Set up method."""
        self.teardown_method()
        self.TMP_ROOT.mkdir(parents=True)
        src = self.SOURCE_DIR / fn
        dest = self.TMP_ROOT / fn
        shutil.copy(src, dest)
        size = self.FNS[fn][0]
        assert dest.stat().st_size == size
        yield
        self.teardown_method()

    def teardown_method(self) -> None:
        """Tear down method."""
        shutil.rmtree(self.TMP_ROOT, ignore_errors=True)
