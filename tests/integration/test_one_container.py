"""Test comic format."""
import shutil
from platform import system

from picopt import PROGRAM_NAME, cli
from tests import CONTAINER_DIR, get_test_dir

__all__ = ()
TMP_ROOT = get_test_dir()
FN = "test_zip.zip"
SRC_CBZ = CONTAINER_DIR / FN

FNS = {FN: (7783, 7015)} if system() == "Darwin" else {FN: (7783, 7015)}


class TestOneContainer:
    """Test containers dir."""

    def setup_method(self) -> None:
        """Set up method."""
        self.teardown_method()
        TMP_ROOT.mkdir(exist_ok=True)
        shutil.copy(SRC_CBZ, TMP_ROOT)
        for name, sizes in FNS.items():
            path = TMP_ROOT / name
            assert path.stat().st_size == sizes[0]

    def teardown_method(self) -> None:
        """Tear down method."""
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)

    def test_containers_no_convert(self) -> None:
        """Test containers no convert."""
        args = (PROGRAM_NAME, "-x", "ZIP", str(TMP_ROOT / FN))
        cli.main(args)
        for name, sizes in FNS.items():
            path = TMP_ROOT / name
            assert path.stat().st_size == sizes[1]
