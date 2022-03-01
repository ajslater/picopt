"""Test the settings module."""
from argparse import Namespace

from confuse import Configuration

from picopt import PROGRAM_NAME, config
from picopt.config import PNG_CONVERTABLE_FORMAT_STRS, WEBP_CONVERTABLE_FORMAT_STRS
from picopt.handlers.gif import Gif
from picopt.handlers.png import Png
from picopt.handlers.zip import CBZ
from tests import get_test_dir


__all__ = ()
FORMATS = set(
    (
        Gif.FORMAT_STR,
        "JPEG",
        Png.FORMAT_STR,
        "WEBP",
    )
)
TMP_ROOT = get_test_dir()
DEEP_PATH = TMP_ROOT / "deep"


class TestConfig:
    def setup_method(self):
        self.config = Configuration(PROGRAM_NAME, PROGRAM_NAME)

    # def teardown_method(self):
    #     pass

    # def _get_attr_dict(self) -> AttrDict:
    #    ad = self.config.get(config.TEMPLATE)
    #    assert isinstance(ad, AttrDict)
    #    return ad

    def test_update_formats(self) -> None:
        config._update_formats(self.config)
        assert self.config["formats"].get() == FORMATS

    def test_update_formats_to_png(self) -> None:
        self.config["convert_to"]["PNG"].set(True)
        config._update_formats(self.config)
        assert self.config["formats"].get() == FORMATS | PNG_CONVERTABLE_FORMAT_STRS

    def test_update_formats_to_webp(self) -> None:
        self.config["convert_to"]["WEBP"].set(True)
        config._update_formats(self.config)
        assert self.config["formats"].get() == FORMATS | WEBP_CONVERTABLE_FORMAT_STRS

    def test_update_formats_cbz(self) -> None:
        self.config["_extra_formats"].set([CBZ.FORMAT_STR])
        config._update_formats(self.config)
        assert self.config["formats"].get() == FORMATS | set([CBZ.FORMAT_STR])

    def test_update(self) -> None:
        args = Namespace(bigger=True)
        assert not self.config["bigger"].get(bool)
        self.config.set_args(args)
        assert self.config["bigger"].get(bool)
