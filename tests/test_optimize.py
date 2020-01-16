"""Test the optimize module."""
import shutil

from pathlib import Path

from picopt import optimize
from picopt.formats.gif import Gif
from picopt.formats.jpeg import Jpeg
from picopt.formats.png import Png
from picopt.settings import Settings
from tests import IMAGES_DIR
from tests import get_test_dir


__all__ = ()  # Hides module from docstring linting
JPEG_SRC = IMAGES_DIR / "test_jpg.jpg"
PNG_SRC = IMAGES_DIR / "test_png.png"
TMP_ROOT = get_test_dir()
OLD_PATH_JPEG = TMP_ROOT / "old.jpeg"
OLD_PATH_PNG = TMP_ROOT / "old.png"
NEW_SIZE = 87922


def _setup(fmt: str = "JPEG") -> Path:
    if fmt == "PNG":
        src = PNG_SRC
        old_path = OLD_PATH_PNG
    else:
        src = JPEG_SRC
        old_path = OLD_PATH_JPEG

    TMP_ROOT.mkdir(exist_ok=True)
    shutil.copy(src, old_path)

    return Path(old_path)


def _teardown() -> None:
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)


def test_optimize_image_external() -> None:
    old_path = _setup()
    old_size = old_path.stat().st_size
    func = Jpeg.PROGRAMS[0]
    res = optimize._optimize_image_external(
        Settings(), old_path, func, "JPEG", old_path.suffix
    )
    assert res.final_path == old_path
    assert res.bytes_in == old_size
    assert res.bytes_out == NEW_SIZE
    _teardown()


def test_optimize_with_progs() -> None:
    fmt = "JPEG"
    old_path = _setup(fmt)
    old_size = old_path.stat().st_size
    res = optimize._optimize_with_progs(Settings(), Jpeg, old_path, fmt)
    assert res.final_path == old_path
    assert res.bytes_in == old_size
    assert res.bytes_out == NEW_SIZE
    _teardown()


def test_optimize_with_progs_no_best() -> None:
    fmt = "PNG"
    old_path = _setup(fmt)
    old_size = old_path.stat().st_size
    res = optimize._optimize_with_progs(Settings(), Png, old_path, fmt)
    old_path.unlink()
    assert res.final_path == old_path
    assert res.bytes_in == old_size
    assert res.bytes_out == 4379  # could change. maybe just > 0
    _teardown()


def test_optimize_with_all_progs_disabled() -> None:
    old_path = _setup()
    settings = Settings()
    settings.mozjpeg = False
    settings.jpegtran = False
    #    settings.jpegrescan = False
    res = optimize._optimize_with_progs(settings, Jpeg, old_path, "JPEG")
    old_path.unlink()
    assert res.final_path == old_path
    assert res.bytes_in == 0
    assert res.bytes_out == 0
    _teardown()


def test_get_format_module_png() -> None:
    cls, nag = optimize._get_format_module(Settings(), "PNG")
    assert cls == Png
    assert not nag


def test_get_format_module_jpeg() -> None:
    cls, nag = optimize._get_format_module(Settings(), "JPEG")
    assert cls == Jpeg
    assert not nag


def test_get_format_module_gif() -> None:
    cls, nag = optimize._get_format_module(Settings(), "ANIMATED_GIF")
    assert cls == Gif
    assert nag


def test_get_format_module_invalid() -> None:
    cls, nag = optimize._get_format_module(Settings(), "")
    assert cls is None
    assert not nag


def test_optimize_image() -> None:
    old_path = _setup()
    old_size = old_path.stat().st_size
    args = (old_path, "JPEG", Settings())
    res = optimize.optimize_image(args)
    assert res.final_path == old_path
    assert res.bytes_in == old_size
    assert res.bytes_out == NEW_SIZE
    _teardown()


def test_optimize_image_none() -> None:
    old_path = _setup()
    args = (old_path, "", Settings())
    res = optimize.optimize_image(args)
    assert res.final_path == old_path
    assert res.bytes_in == 0
    assert res.bytes_out == 0
    assert res.error == "File format not selected."
    _teardown()


def test_optimize_image_none_quiet() -> None:
    old_path = _setup()
    settings = Settings()
    settings.verbose = 1
    args = (old_path, "", settings)
    res = optimize.optimize_image(args)
    assert res.final_path == old_path
    assert res.bytes_in == 0
    assert res.bytes_out == 0
    assert res.error == "File format not selected."
    _teardown()


def test_optimize_image_error() -> None:
    old_path = Path("")
    args = (old_path, "JPEG", Settings())
    res = optimize.optimize_image(args)
    assert res.final_path == old_path
    assert res.bytes_in == 0
    assert res.bytes_out == 0
    assert res.error == "Optimizing Image"
    _teardown()
