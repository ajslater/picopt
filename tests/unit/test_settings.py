"""Test the settings module."""
from argparse import Namespace
from sys import platform

from picopt.formats.gif import Gif
from picopt.formats.png import Png
from picopt.settings import Settings


__all__ = ()
FORMATS = set(["ANIMATED_GIF", "PNG", "PNM", "BMP", "PPM", "JPEG", "GIF"])
TEST_PROGS = set(Png.PROGRAMS + Gif.PROGRAMS)


def test_parse_date_string() -> None:
    res = Settings.parse_date_string("2020-Jan-10 10:25:03pm")
    if platform == "darwin":
        assert res == 1578723903.0
    elif platform == "linux":
        assert res == 1578695103.0


def test_update_formats() -> None:
    settings = Settings()
    settings._update_formats()
    assert settings.formats == FORMATS


def test_update_formats_to_png() -> None:
    settings = Settings()
    settings.to_png_formats = set(["PNG"])
    settings._update_formats()
    assert settings.formats == FORMATS


def test_update_formats_png() -> None:
    settings = Settings()
    png_only = set(["PNG"])
    settings.formats = png_only
    settings._update_formats()
    assert settings.formats == png_only


def test_update_formats_comics() -> None:
    settings = Settings()
    settings.comics = True
    settings._update_formats()
    assert settings.formats == FORMATS | set(["CBZ", "CBR"])


# def test_set_jpegrescan_threading_one() -> None:
#    settings = Settings()
#    paths = set(["tests/test_files/images/test_png.png"])
#    settings.paths = paths
#    assert settings.jpegrescan_multithread


# def test_set_jpegrescan_threading_many() -> None:
#    settings = Settings()
#    paths = Path("tests/test_files/images").glob("*.png")
#    strs = [str(path) for path in paths]
#    settings.paths = set(strs)
#    settings._set_jpegrescan_threading()
#    assert settings.jpegrescan_multithread


# def test_set_jpegrescan_threading_files_dir() -> None:
#    settings = Settings()
#    settings.paths = set(["tests/test_files/images"])
#    settings._set_jpegrescan_threading()
#    assert not settings.jpegrescan_multithread


# def test_set_jpegrescan_threading_files_invalid() -> None:
#    settings = Settings()
#    settings.paths = set(["XXX"])
#    settings._set_jpegrescan_threading()
#    assert not settings.jpegrescan_multithread


def test_update() -> None:
    args = Namespace(bigger=True)
    settings = Settings()
    assert not settings.bigger
    settings._update(args)
    assert settings.bigger


def test_update_underscore() -> None:
    args = Namespace(_fake=True)
    settings = Settings()
    assert not hasattr(settings, "_fake")
    settings._update(args)
    assert not hasattr(settings, "_fake")


def test_set_program_defaults() -> None:
    settings = Settings()
    settings._set_program_defaults(TEST_PROGS)
    for program in TEST_PROGS:
        name = program.__func__.__name__  # type: ignore
        assert getattr(settings, name)


def test_config_program_reqs() -> None:
    settings = Settings()
    settings._config_program_reqs(TEST_PROGS)
    assert settings.can_do
