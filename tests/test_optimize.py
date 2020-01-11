"""Test the optimize module."""
import shutil

from pathlib import Path

from picopt import optimize
from picopt.formats.gif import Gif
from picopt.formats.jpeg import Jpeg
from picopt.formats.png import Png
from picopt.settings import Settings


__all__ = ()  # Hides module from docstring linting
TEST_FILES_ROOT = Path("tests/test_files")
IMAGES_ROOT = TEST_FILES_ROOT / "images"
JPEG_SRC = IMAGES_ROOT / "test_jpg.jpg"
PNG_SRC = IMAGES_ROOT / "test_png.png"
TMP_PATH = Path("/tmp")
OLD_PATH_JPEG = TMP_PATH / "old.jpeg"
OLD_PATH_PNG = TMP_PATH / "old.png"
NEW_SIZE = 87922


def _setup_optimize(fmt="JPEG"):
    if fmt == "PNG":
        src = PNG_SRC
        old_path = OLD_PATH_PNG
    else:
        src = JPEG_SRC
        old_path = OLD_PATH_JPEG

    shutil.copy(src, old_path)

    return old_path


def test_optimize_image_external():
    old_path = _setup_optimize()
    old_size = old_path.stat().st_size
    func = Jpeg.PROGRAMS[0]
    res = optimize._optimize_image_external(
        Settings(), old_path, func, "JPEG", old_path.suffix
    )
    old_path.unlink()
    assert res.final_path == old_path
    assert res.bytes_in == old_size
    assert res.bytes_out == NEW_SIZE


def test_optimize_with_progs():
    fmt = "JPEG"
    old_path = _setup_optimize(fmt)
    old_size = old_path.stat().st_size
    res = optimize._optimize_with_progs(Settings(), Jpeg, old_path, fmt)
    old_path.unlink()
    assert res.final_path == old_path
    assert res.bytes_in == old_size
    assert res.bytes_out == NEW_SIZE


def test_optimize_with_progs_no_best():
    fmt = "PNG"
    old_path = _setup_optimize(fmt)
    old_size = old_path.stat().st_size
    res = optimize._optimize_with_progs(Settings(), Png, old_path, fmt)
    old_path.unlink()
    assert res.final_path == old_path
    assert res.bytes_in == old_size
    assert res.bytes_out == 4379  # could change. maybe just > 0


def test_optimize_with_all_progs_disabled():
    old_path = _setup_optimize()
    settings = Settings()
    settings.mozjpeg = False
    settings.jpegtran = False
    settings.jpegrescan = False
    res = optimize._optimize_with_progs(settings, Jpeg, old_path, "JPEG")
    old_path.unlink()
    assert res.final_path == old_path
    assert res.bytes_in == 0
    assert res.bytes_out == 0


def test_get_format_module_png():
    cls, nag = optimize._get_format_module(Settings(), "PNG")
    assert cls == Png
    assert not nag


def test_get_format_module_jpeg():
    cls, nag = optimize._get_format_module(Settings(), "JPEG")
    assert cls == Jpeg
    assert not nag


def test_get_format_module_gif():
    cls, nag = optimize._get_format_module(Settings(), "ANIMATED_GIF")
    assert cls == Gif
    assert nag


def test_get_format_module_invalid():
    cls, nag = optimize._get_format_module(Settings(), "")
    assert cls is None
    assert not nag


def test_optimize_image():
    old_path = _setup_optimize()
    old_size = old_path.stat().st_size
    args = (old_path, "JPEG", Settings())
    res = optimize.optimize_image(args)
    assert res.final_path == old_path
    assert res.bytes_in == old_size
    assert res.bytes_out == NEW_SIZE
    old_path.unlink()


def test_optimize_image_none():
    old_path = _setup_optimize()
    args = (old_path, "", Settings())
    res = optimize.optimize_image(args)
    assert res.final_path == old_path
    assert res.bytes_in == 0
    assert res.bytes_out == 0
    assert res.error == "File format not selected."
    old_path.unlink()


def test_optimize_image_none_quiet():
    old_path = _setup_optimize()
    settings = Settings()
    settings.verbose = 1
    args = (old_path, "", settings)
    res = optimize.optimize_image(args)
    assert res.final_path == old_path
    assert res.bytes_in == 0
    assert res.bytes_out == 0
    assert res.error == "File format not selected."
    old_path.unlink()


def test_optimize_image_error():
    old_path = Path("")
    args = (old_path, "JPEG", Settings())
    res = optimize.optimize_image(args)
    assert res.final_path == old_path
    assert res.bytes_in == 0
    assert res.bytes_out == 0
    assert res.error == "Optimizing Image"
