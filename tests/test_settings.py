from unittest import TestCase

from picopt.settings import Settings

class TestSettings(TestCase):

    class DummySettings(object):
        bigger = True

    def test_update(self):
        self.assertFalse(Settings.bigger)
        Settings.update(self.DummySettings)
        self.assertTrue(Settings.bigger)
