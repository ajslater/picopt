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


class TestOptimize:
    fmt = "JPEG"

    def setup_png(self):
        self.fmt = "PNG"
        src = PNG_SRC
        self.old_path = OLD_PATH_PNG
        shutil.copy(src, self.old_path)

    def setup_method(self) -> None:
        src = JPEG_SRC
        self.old_path = OLD_PATH_JPEG

        TMP_ROOT.mkdir(exist_ok=True)
        shutil.copy(src, self.old_path)
        self.settings = Settings()

    def teardown_method(self) -> None:
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)

    def test_optimize_image_external(self) -> None:
        old_size = self.old_path.stat().st_size
        func = Jpeg.PROGRAMS[0]
        res = optimize._optimize_image_external(
            self.settings, self.old_path, func, "JPEG", self.old_path.suffix
        )
        assert res.final_path == self.old_path
        assert res.bytes_in == old_size
        assert res.bytes_out == NEW_SIZE

    def test_optimize_with_progs(self) -> None:
        old_size = self.old_path.stat().st_size
        res = optimize._optimize_with_progs(
            self.settings, Jpeg, self.old_path, self.fmt
        )
        assert res.final_path == self.old_path
        assert res.bytes_in == old_size
        assert res.bytes_out == NEW_SIZE

    def test_optimize_with_progs_no_best(self) -> None:
        self.setup_png()
        old_size = self.old_path.stat().st_size
        res = optimize._optimize_with_progs(self.settings, Png, self.old_path, self.fmt)
        # old_path.unlink()
        assert res.final_path == self.old_path
        assert res.bytes_in == old_size
        assert res.bytes_out == 4379  # could change. maybe just > 0

    def test_optimize_with_all_progs_disabled(self) -> None:
        self.settings.mozjpeg = False
        self.settings.jpegtran = False
        #    settings.jpegrescan = False
        res = optimize._optimize_with_progs(
            self.settings, Jpeg, self.old_path, self.fmt
        )
        # old_path.unlink()
        assert res.final_path == self.old_path
        assert res.bytes_in == 0
        assert res.bytes_out == 0

    def test_optimize_image(self) -> None:
        old_size = self.old_path.stat().st_size
        args = (self.old_path, self.fmt, self.settings)
        res = optimize.optimize_image(args)
        assert res.final_path == self.old_path
        assert res.bytes_in == old_size
        assert res.bytes_out == NEW_SIZE

    def test_optimize_image_none(self) -> None:
        args = (self.old_path, "", self.settings)
        res = optimize.optimize_image(args)
        assert res.final_path == self.old_path
        assert res.bytes_in == 0
        assert res.bytes_out == 0
        assert res.error == "File format not selected."

    def test_optimize_image_none_quiet(self) -> None:
        self.settings.verbose = 1
        args = (self.old_path, "", self.settings)
        res = optimize.optimize_image(args)
        assert res.final_path == self.old_path
        assert res.bytes_in == 0
        assert res.bytes_out == 0
        assert res.error == "File format not selected."

    def test_optimize_image_none_verbose(self) -> None:
        self.settings.verbose = 2
        args = (self.old_path, "", self.settings)
        res = optimize.optimize_image(args)
        assert res.final_path == self.old_path
        assert res.bytes_in == 0
        assert res.bytes_out == 0
        assert res.error == "File format not selected."

    def test_optimize_image_error(self) -> None:
        self.old_path = Path("")
        args = (self.old_path, self.fmt, self.settings)
        res = optimize.optimize_image(args)
        assert res.final_path == self.old_path
        assert res.bytes_in == 0
        assert res.bytes_out == 0
        assert res.error == "Optimizing Image"


class TestOptimizeGetFormat:
    def setup_method(self):
        self.settings = Settings()

    def test_get_format_module_png(self) -> None:
        cls, nag = optimize._get_format_module(self.settings, "PNG")
        assert cls == Png
        assert not nag

    def test_get_format_module_jpeg(self) -> None:
        cls, nag = optimize._get_format_module(self.settings, "JPEG")
        assert cls == Jpeg
        assert not nag

    def test_get_format_module_gif(self) -> None:
        cls, nag = optimize._get_format_module(self.settings, "ANIMATED_GIF")
        assert cls == Gif
        assert nag

    def test_get_format_module_invalid(self) -> None:
        cls, nag = optimize._get_format_module(self.settings, "")
        assert cls is None
        assert not nag
