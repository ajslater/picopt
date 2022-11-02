"""Test comic format."""
import shutil

from platform import system
from zipfile import ZipFile

from picopt import PROGRAM_NAME, cli
from tests import CONTAINER_DIR, get_test_dir


__all__ = ()
TMP_ROOT = get_test_dir()
SRC_CBZ = CONTAINER_DIR / "test_cbz.cbz"

if system() == "Darwin":
    FNS = {
        "test_cbz.cbz": (93408, 84493, ("cbz", 93408)),
        "test_cbr.cbr": (93725, 93725, ("cbz", 84506)),
        "test_rar.rar": (93675, 93675, ("zip", 84493)),
        "test_zip.zip": (2974, 1871, ("zip", 2974)),
        "igp-twss.epub": (292448, 281248, ("epub", 292448)),
    }
else:
    FNS = {
        "test_cbz.cbz": (93408, 84481, ("cbz", 93408)),
        "test_cbr.cbr": (93725, 93725, ("cbz", 84494)),
        "test_rar.rar": (93675, 93675, ("zip", 84481)),
        "test_zip.zip": (2974, 1917, ("zip", 2974)),
        "igp-twss.epub": (292448, 280700, ("epub", 292448)),
    }


class TestContainersDir:
    def setup_method(self) -> None:
        self.teardown_method()
        shutil.copytree(CONTAINER_DIR, TMP_ROOT)
        for name, sizes in FNS.items():
            path = TMP_ROOT / name
            assert path.stat().st_size == sizes[0]

    def teardown_method(self) -> None:
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)

    def test_containers_noop(self) -> None:
        args = (PROGRAM_NAME, "-r", str(TMP_ROOT))
        res = cli.main(args)
        assert res
        for name, sizes in FNS.items():
            if name == "igp-twss.epub":
                path = TMP_ROOT / name
                with ZipFile(path, "r") as zf:
                    namelist = zf.namelist()
                assert "OPS/test_bmp.bmp" in namelist
            path = TMP_ROOT / name
            assert path.stat().st_size == sizes[0]

    def test_containers_no_convert(self) -> None:
        args = (PROGRAM_NAME, "-rx", "CBZ,ZIP,EPUB", "-c WEBP", str(TMP_ROOT))
        res = cli.main(args)
        assert res
        for name, sizes in FNS.items():
            path = TMP_ROOT / name
            if name == "igp-twss.epub":
                with ZipFile(path, "r") as zf:
                    namelist = zf.namelist()
                assert "OPS/test_bmp.bmp" in namelist
            assert path.stat().st_size == sizes[1]

    def test_containers_convert_to_zip(self) -> None:
        args = (PROGRAM_NAME, "-rc", "ZIP,CBZ", str(TMP_ROOT))
        res = cli.main(args)
        assert res
        for name, sizes in FNS.items():
            path = (TMP_ROOT / name).with_suffix("." + sizes[2][0])
            assert path.stat().st_size == sizes[2][1]
