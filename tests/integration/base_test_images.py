"""Base class for testing images."""
import shutil
from abc import ABC
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from tests import IMAGES_DIR, get_test_dir


class BaseTestImagesDir(ABC):
    """Test images dir."""

    FNS: Mapping = MappingProxyType({})
    TMP_ROOT: Path = get_test_dir()

    def setup_method(self) -> None:
        """Set up method."""
        self.teardown_method()
        self.TMP_ROOT.mkdir(parents=True)
        for fn, sizes in self.FNS.items():
            src = IMAGES_DIR / fn
            dest = self.TMP_ROOT / fn
            shutil.copy(src, dest)
            assert dest.stat().st_size == sizes[0]

    def teardown_method(self) -> None:
        """Tear down method."""
        shutil.rmtree(self.TMP_ROOT, ignore_errors=True)
