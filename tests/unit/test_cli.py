"""Test cli module."""
import shutil
import sys

from picopt import cli
from picopt.handlers.zip import CBZ, Zip
from tests import IMAGES_DIR, get_test_dir


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

    def test_get_arguments(self) -> None:
        args = ("picopt", "-rqc", "PNG,WEBP", "-x", "CBZ,ZIP", "-bTLM", str(TMP_ROOT))
        arguments = cli.get_arguments(args)
        arguments = arguments.picopt
        assert arguments.verbose == 0
        assert ("PNG", "WEBP") == arguments.convert_to
        assert arguments.formats is None
        assert arguments._extra_formats == (CBZ.OUTPUT_FORMAT, Zip.OUTPUT_FORMAT)
        assert arguments.symlinks
        assert arguments.bigger
        assert not arguments.timestamps
        assert arguments.test
        assert arguments.list_only
        assert not arguments.keep_metadata
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
