from unittest import TestCase

from picopt import settings


class TestSettings(TestCase):

    class DummySettings(object):
        bigger = True

    def test_update(self):
        self.assertFalse(settings.Settings.bigger)
        settings.Settings.update(self.DummySettings)
        self.assertTrue(settings.Settings.bigger)
