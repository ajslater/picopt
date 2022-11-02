"""Test comic format."""
import shutil

from platform import system

from picopt import PROGRAM_NAME, cli
from tests import CONTAINER_DIR, get_test_dir


__all__ = ()
TMP_ROOT = get_test_dir()
FN = "test_zip.zip"
SRC_CBZ = CONTAINER_DIR / FN

if system() == "Darwin":
    FNS = {
        FN: (2974, 1871),
    }
else:
    FNS = {
        FN: (2974, 1917),
    }


class TestContainersDir:
    def setup_method(self) -> None:
        self.teardown_method()
        TMP_ROOT.mkdir(exist_ok=True)
        shutil.copy(SRC_CBZ, TMP_ROOT)
        for name, sizes in FNS.items():
            path = TMP_ROOT / name
            assert path.stat().st_size == sizes[0]

    def teardown_method(self) -> None:
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)

    def test_containers_no_convert(self) -> None:
        args = (PROGRAM_NAME, "-x", "ZIP", str(TMP_ROOT / FN))
        res = cli.main(args)
        assert res
        for name, sizes in FNS.items():
            path = TMP_ROOT / name
            assert path.stat().st_size == sizes[1]
