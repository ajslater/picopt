"""Test cli module."""
import shutil
import sys

from picopt import cli
from tests import IMAGES_DIR
from tests import get_test_dir


__all__ = ()  # hides module from pydocstring
TYPE_NAME = "png"
TMP_ROOT = get_test_dir()
JPEG_SRC = IMAGES_DIR / "test_jpg.jpg"


class TestCLI:
    OLD_PATH = TMP_ROOT / "old.jpg"

    def setup_method(self) -> None:
        TMP_ROOT.mkdir(exist_ok=True)

    def teardown_method(self) -> None:
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)

    def test_csv_set(self) -> None:
        res = cli.csv_set("a,b,c,d")
        assert res == set(("A", "B", "C", "D"))

    def test_get_arguments(self) -> None:
        args = ("picopt", "-vQcYSbINlM", str(TMP_ROOT))
        arguments = cli.get_arguments(args)
        assert arguments.verbose == -1
        # assert arguments.advpng
        assert arguments.comics
        assert arguments.formats is None
        #    assert not arguments.jpegrescan
        assert arguments.to_png_formats == set(["PNG"])
        assert not arguments.follow_symlinks
        assert arguments.bigger
        assert not arguments.record_timestamp
        assert arguments.test
        assert arguments.list_only
        assert arguments.destroy_metadata
        assert arguments.paths[0] == str(TMP_ROOT)

    def test_main(self) -> None:
        shutil.copy(JPEG_SRC, self.OLD_PATH)
        old_size = self.OLD_PATH.stat().st_size
        sys.argv = ["picopt", str(self.OLD_PATH)]
        cli.main()
        assert self.OLD_PATH.is_file()
        assert self.OLD_PATH.stat().st_size < old_size

    def test_main_err(self) -> None:
        sys.argv = ["picopt", "XXX"]
        try:
            cli.main()
        except SystemExit as exc:
            assert exc.code == 1
