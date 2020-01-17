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


def test_csv_set() -> None:
    res = cli.csv_set("a,b,c,d")
    assert res == set(("A", "B", "C", "D"))


def test_get_arguments() -> None:
    args = ("picopt", "-rvQcOPEZTGYSbtNlM", str(TMP_ROOT))
    arguments = cli.get_arguments(args)
    assert arguments.recurse
    assert arguments.verbose == -1
    # assert arguments.advpng
    assert arguments.comics
    assert arguments.formats == set()
    assert not arguments.optipng
    assert not arguments.pngout
    #    assert not arguments.jpegrescan
    assert not arguments.mozjpeg
    assert not arguments.jpegtran
    assert not arguments.gifsicle
    assert arguments.to_png_formats == set(["PNG"])
    assert not arguments.follow_symlinks
    assert arguments.bigger
    assert arguments.record_timestamp
    assert arguments.test
    assert arguments.list_only
    assert arguments.destroy_metadata
    assert arguments.paths[0] == str(TMP_ROOT)


def _setup() -> None:
    TMP_ROOT.mkdir(exist_ok=True)


def _teardown() -> None:
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)


def test_main() -> None:
    _setup()
    old_path = TMP_ROOT / "old.jpg"
    shutil.copy(JPEG_SRC, old_path)
    old_size = old_path.stat().st_size
    sys.argv = ["picopt", str(old_path)]
    cli.main()
    assert old_path.is_file()
    assert old_path.stat().st_size < old_size
    _teardown()


def test_main_err() -> None:
    sys.argv = ["picopt", "-OPZTG", "XXX"]
    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 1
