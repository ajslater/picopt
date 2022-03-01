"""Test the optimize module."""
import shutil

from pathlib import Path

from confuse.templates import AttrDict

from picopt import optimize
from picopt.handlers.jpeg import Jpeg
from picopt.handlers.png import Png
from tests import IMAGES_DIR, get_test_dir


__all__ = ()  # Hides module from docstring linting
JPEG_SRC = IMAGES_DIR / "test_jpg.jpg"
PNG_SRC = IMAGES_DIR / "test_png.png"
TMP_ROOT = get_test_dir()
OLD_PATH_JPEG = TMP_ROOT / "old.jpeg"
OLD_PATH_PNG = TMP_ROOT / "old.png"
NEW_SIZE = 87913
TMP_SUFFIX = ".tmp"


class TestOptimize:
    fmt = "JPEG"

    def setup_png(self):
        self.fmt_cls = Png
        src = PNG_SRC
        self.old_path = OLD_PATH_PNG
        shutil.copy(src, self.old_path)

    def setup_method(self) -> None:
        src = JPEG_SRC
        self.old_path = OLD_PATH_JPEG
        self.tmp_path = Path(str(OLD_PATH_JPEG) + TMP_SUFFIX)

        TMP_ROOT.mkdir(exist_ok=True)
        shutil.copy(src, self.old_path)
        self.config = AttrDict()

    def teardown_method(self) -> None:
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)

    def test_optimize_image_external(self) -> None:
        old_size = self.old_path.stat().st_size
        func = Jpeg.PROGRAMS[0]
        res = optimize._optimize_image_external(
            self.config,
            self.old_path,
            self.tmp_path,
            func,
        )
        assert res.final_path == self.old_path
        assert res.bytes_in == old_size
        assert res.bytes_out == NEW_SIZE

    def test_optimize_with_progs(self) -> None:
        old_size = self.old_path.stat().st_size
        res = optimize._optimize_with_progs(self.config, Jpeg, self.old_path)
        assert res.final_path == self.old_path
        assert res.bytes_in == old_size
        assert res.bytes_out == NEW_SIZE

    def test_optimize_with_progs_no_best(self) -> None:
        self.setup_png()
        old_size = self.old_path.stat().st_size
        res = optimize._optimize_with_progs(self.config, Png, self.old_path)
        assert res.final_path == self.old_path
        assert res.bytes_in == old_size
        assert res.bytes_out == 4379  # could change. maybe just > 0

    def test_optimize_with_all_progs_disabled(self) -> None:
        self.config.mozjpeg = False
        self.config.jpegtran = False
        res = optimize._optimize_with_progs(self.config, Jpeg, self.old_path)
        assert res.final_path == self.old_path
        assert res.bytes_in == 0
        assert res.bytes_out == 0

    def test_optimize_image(self) -> None:
        old_size = self.old_path.stat().st_size
        args = (self.old_path, self.fmt_cls, self.config)
        res = optimize.optimize_image(args)
        assert res.final_path == self.old_path
        assert res.bytes_in == old_size
        assert res.bytes_out == NEW_SIZE

    def test_optimize_image_error(self) -> None:
        self.old_path = Path("")
        args = (self.old_path, self.fmt_cls, self.config)
        res = optimize.optimize_image(args)
        assert res.final_path == self.old_path
        assert res.bytes_in == 0
        assert res.bytes_out == 0
        assert res.error == "Optimizing Image"
