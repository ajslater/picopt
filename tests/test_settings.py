from unittest import TestCase

from picopt.settings import Settings

class TestSettingsUpdate(TestCase):

    class DummySettings(object):
        bigger = True

    def test_update(self):
        self.assertFalse(Settings.bigger)
        Settings.update(self.DummySettings)
        self.assertTrue(Settings.bigger)


class TestSettingsSetProgramDefaults(TestCase):

    @staticmethod
    def true():
        pass

    @staticmethod
    def false():
        pass

    @staticmethod
    def DOESNOTEXIST():
        pass

    class DummySettingsObject(Settings):
        true = True
        false = True
        DOESNOTEXIST = True

    def test_set_program_defaults(self):
        programs = [self.true, self.false, self.DOESNOTEXIST]

        self.DummySettingsObject._set_program_defaults(programs)

        self.assertTrue(getattr(self.DummySettingsObject,
                                programs[0].__name__))
        self.assertTrue(getattr(self.DummySettingsObject,
                                programs[1].__name__))
        self.assertFalse(getattr(self.DummySettingsObject,
                                 programs[2].__name__))
