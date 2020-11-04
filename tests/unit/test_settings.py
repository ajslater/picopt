"""Test the settings module."""
import shutil

from argparse import Namespace
from sys import platform

from ruamel.yaml import YAML

from picopt.formats.gif import Gif
from picopt.formats.png import Png
from picopt.settings import RC_FN
from picopt.settings import Settings
from tests import get_test_dir


__all__ = ()
FORMATS = set(["ANIMATED_GIF", "PNG", "PNM", "BMP", "PPM", "JPEG", "GIF"])
TEST_PROGS = set(Png.PROGRAMS + Gif.PROGRAMS)
TMP_ROOT = get_test_dir()
RC_PATH = TMP_ROOT / RC_FN
RC_SETTINGS = {"jpegtran": False}


class TestSettings:
    def setup_method(self):
        self.settings = Settings()

    def teardown_method(self):
        pass

    def test_parse_date_string(self) -> None:
        res = Settings.parse_date_string("2020-Jan-10 10:25:03pm")
        if platform == "darwin":
            assert res == 1578723903.0
        elif platform == "linux":
            assert res == 1578695103.0

    def test_update_formats(self) -> None:
        self.settings._update_formats()
        assert self.settings.formats == FORMATS

    def test_update_formats_to_png(self) -> None:
        self.settings.to_png_formats = set(["PNG"])
        self.settings._update_formats()
        assert self.settings.formats == FORMATS

    def test_update_formats_png(self) -> None:
        png_only = set(["PNG"])
        self.settings.formats = png_only
        self.settings._update_formats()
        assert self.settings.formats == png_only

    def test_update_formats_comics(self) -> None:
        self.settings.comics = True
        self.settings._update_formats()
        assert self.settings.formats == FORMATS | set(["CBZ", "CBR"])

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

    def test_update(self) -> None:
        args = Namespace(bigger=True)
        assert not self.settings.bigger
        self.settings._update(args)
        assert self.settings.bigger

    def test_update_underscore(self) -> None:
        args = Namespace(_fake=True)
        assert not hasattr(self.settings, "_fake")
        self.settings._update(args)
        assert not hasattr(self.settings, "_fake")

    def test_set_program_defaults(self) -> None:
        self.settings._set_program_defaults()
        for program in TEST_PROGS:
            name = program.__func__.__name__  # type: ignore
            assert getattr(self.settings, name)

    def test_config_program_reqs(self) -> None:
        self.settings._config_program_reqs()
        assert self.settings.can_do


class TestRCSettings:

    yaml = YAML()

    def setup_method(self):
        self.teardown_method()
        TMP_ROOT.mkdir(parents=True)
        self.yaml.dump(RC_SETTINGS, RC_PATH)
        self.settings = Settings(rc_path=TMP_ROOT)

    def teardown_method(self):
        if TMP_ROOT.is_dir():
            shutil.rmtree(TMP_ROOT)

    def test_load_rc(self):
        rc_settings = self.settings.load_rc(RC_PATH)
        assert rc_settings == Namespace(**RC_SETTINGS)

    def test_load_rc_apply(self):
        assert not self.settings.jpegtran
