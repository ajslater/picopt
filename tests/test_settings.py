"""Test the settings module."""
from unittest import TestCase

from picopt.settings import Settings


class TestSettingsUpdate(TestCase):

    class DummySettings(object):
        bigger: bool = True

    def test_update(self) -> None:
        self.assertFalse(Settings.bigger)
        Settings.update(self.DummySettings)
        self.assertTrue(Settings.bigger)


class TestSettingsSetProgramDefaults(TestCase):

    @staticmethod
    def true() -> None:
        pass

    @staticmethod
    def false() -> None:
        pass

    @staticmethod
    def does_not_exist() -> None:
        pass

    class DummySettingsObject(Settings):
        true: bool = True
        false: bool = True
        DOESNOTEXIST: bool = True

    def test_set_program_defaults(self) -> None:
        programs = [self.true, self.false, self.does_not_exist]

        self.DummySettingsObject._set_program_defaults(programs)

        self.assertTrue(getattr(self.DummySettingsObject,
                                programs[0].__name__))
        self.assertTrue(getattr(self.DummySettingsObject,
                                programs[1].__name__))
        self.assertFalse(getattr(self.DummySettingsObject,
                                 programs[2].__name__))
