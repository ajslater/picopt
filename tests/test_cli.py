"""Test stats commands."""
from pathlib import Path

from picopt import cli


# from picopt.settings import Settings


__all__ = ()  # hides module from pydocstring

TYPE_NAME = "png"
PATH = Path("dummyPath")


def test_csv_set() -> None:
    res = cli.csv_set("a,b,c,d")
    assert res == set(("A", "B", "C", "D"))


def test_get_arguments() -> None:
    args = ("picopt", "-rvQacOPJEZTGYSbtNlM", str(PATH))
    arguments = cli.get_arguments(args)
    assert arguments.recurse
    assert arguments.verbose == -1
    assert arguments.advpng
    assert arguments.comics
    assert arguments.formats == set()
    assert not arguments.optipng
    assert not arguments.pngout
    assert not arguments.jpegrescan
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
    assert arguments.paths[0] == str(PATH)


def test_main():
    import sys

    sys.argv = ["picopt", "-h"]
    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 0


# TODO import test run from the cli directory probably
