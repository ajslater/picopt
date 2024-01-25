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
        "test_zip.zip": (2974, 2921, ("zip", 2974)),
        "igp-twss.epub": (292448, 281248, ("epub", 292448)),
    }
else:
    FNS = {
        "test_cbz.cbz": (93408, 84493, ("cbz", 93408)),
        "test_cbr.cbr": (93725, 93725, ("cbz", 84506)),
        "test_rar.rar": (93675, 93675, ("zip", 84493)),
        "test_zip.zip": (2974, 2921, ("zip", 2974)),
        "igp-twss.epub": (292448, 281248, ("epub", 292448)),
    }

EPUB_FN = "igp-twss.epub"
BMP_FN = "OPS/test_bmp.bmp"


class TestContainersDir:
    """Test containers dirs."""

    def setup_method(self) -> None:
        """Set up method."""
        self.teardown_method()
        shutil.copytree(CONTAINER_DIR, TMP_ROOT)
        for name, sizes in FNS.items():
            path = TMP_ROOT / name
            assert path.stat().st_size == sizes[0]

    def teardown_method(self) -> None:
        """Tear down method."""
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)

    def test_containers_noop(self) -> None:
        """Test containers noop."""
        args = (PROGRAM_NAME, "-r", str(TMP_ROOT))
        cli.main(args)
        for name, sizes in FNS.items():
            if name == EPUB_FN:
                path = TMP_ROOT / name
                with ZipFile(path, "r") as zf:
                    namelist = zf.namelist()
                assert BMP_FN in namelist
            path = TMP_ROOT / name
            assert path.stat().st_size == sizes[0]

    def test_containers_no_convert(self) -> None:
        """Test containers no convert."""
        args = (PROGRAM_NAME, "-rx", "CBZ,ZIP,EPUB", "-c WEBP", str(TMP_ROOT))
        cli.main(args)
        for name, sizes in FNS.items():
            path = TMP_ROOT / name
            if name == EPUB_FN:
                with ZipFile(path, "r") as zf:
                    namelist = zf.namelist()
                assert BMP_FN in namelist
            assert path.stat().st_size == sizes[1]

    def test_containers_convert_to_zip(self) -> None:
        """Test containers convert to zip."""
        args = (PROGRAM_NAME, "-rc", "ZIP,CBZ", str(TMP_ROOT))
        cli.main(args)
        for name, sizes in FNS.items():
            path = (TMP_ROOT / name).with_suffix("." + sizes[2][0])
            assert path.stat().st_size == sizes[2][1]
