"""Test the settings module."""
import shutil

from argparse import Namespace

from ruamel.yaml import YAML

from picopt.formats.gif import Gif
from picopt.formats.png import Png
from picopt.settings import Settings
from tests import get_test_dir


__all__ = ()
FORMATS = set(["ANIMATED_GIF", "PNG", "PNM", "BMP", "PPM", "JPEG", "GIF"])
TEST_PROGS = set(Png.PROGRAMS + Gif.PROGRAMS)
TMP_ROOT = get_test_dir()
DEEP_PATH = TMP_ROOT / "deep"
RC_PATH = TMP_ROOT / Settings._RC_NAME
RC_SETTINGS = {"jpegtran": False, "formats": FORMATS}
RC_NAMESPACE = Namespace(**RC_SETTINGS)


class TestSettings:
    def setup_method(self):
        self.settings = Settings()

    def teardown_method(self):
        pass

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
        with open(RC_PATH) as rc:
            print(rc.read())
        rc_settings = self.settings.load_rc(RC_PATH)
        assert rc_settings == RC_NAMESPACE

    def test_load_rc_apply(self):
        assert not self.settings.jpegtran

    def test_load_settings_set_verbose(self):
        self.settings.verbose = 2
        self.settings.load_settings(TMP_ROOT)
        assert self.settings.formats == FORMATS

    def test_load_rc_deep(self):
        rc_settings = self.settings.load_rc(DEEP_PATH)
        assert rc_settings == Namespace(**RC_SETTINGS)


class TestNoRC:
    def setup_method(self):
        self.teardown_method()
        TMP_ROOT.mkdir(parents=True)
        self.settings = Settings(rc_path=TMP_ROOT)

    def teardown_method(self):
        if TMP_ROOT.is_dir():
            shutil.rmtree(TMP_ROOT)

    def test_load_rc_deep(self):
        DEEP_PATH.mkdir(parents=True)
        rc_settings = self.settings.load_rc(DEEP_PATH)
        assert rc_settings == Namespace()

    def test_clone(self):
        yaml = YAML()
        yaml.dump(RC_SETTINGS, RC_PATH)
        clone = self.settings.clone(RC_PATH)
        assert self.settings.jpegtran
        assert not clone.jpegtran


class TestSettingsCheck:
    def test_settings_init_check(self):
        settings = Settings(check_programs=True)
        assert settings.can_do
