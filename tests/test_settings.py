"""Test the settings module."""
from argparse import Namespace
from typing import List
from unittest import TestCase

from picopt.extern import ExtArgs
from picopt.formats.format import Format
from picopt.settings import Settings


class TestSettingsUpdate(TestCase):

    def test_update(self) -> None:
        args = Namespace(bigger=True)
        self.assertFalse(Settings.bigger)
        Settings.update(args)
        self.assertTrue(Settings.bigger)


class DummyFormat(Format):
    @staticmethod
    def true(args: ExtArgs) -> str:
        return 'foo'

    @staticmethod
    def false(args: ExtArgs) -> str:
        return 'foo'

    @staticmethod
    def does_not_exist(args: ExtArgs) -> str:
        return 'foo'

    PROGRAMS = (true, false, does_not_exist)


class TestSettingsSetProgramDefaults(TestCase):

    class DummySettingsObject(Settings):
        true: bool = True
        false: bool = True
        does_not_exist: bool = True

    def test_set_program_defaults(self) -> None:

        programs = DummyFormat.PROGRAMS
        self.DummySettingsObject._set_program_defaults(set(programs))

        names: List[str] = []
        for program in programs:
            names += [program.__func__.__name__]  # type: ignore

        self.assertTrue(getattr(self.DummySettingsObject, names[0]))
        self.assertTrue(getattr(self.DummySettingsObject, names[1]))
        self.assertFalse(getattr(self.DummySettingsObject, names[2]))
