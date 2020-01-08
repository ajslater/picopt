"""Test the settings module."""
from argparse import Namespace
from typing import List
from unittest import TestCase

from picopt.extern import ExtArgs
from picopt.formats.format import Format
from picopt.settings import Settings


__all__ = ()


class TestSettingsUpdate(TestCase):
    def test_update(self) -> None:
        args = Namespace(bigger=True)
        settings = Settings()
        self.assertFalse(settings.bigger)
        settings._update(args)
        self.assertTrue(settings.bigger)


class DummyFormat(Format):
    @staticmethod
    def true(settings: Settings, args: ExtArgs) -> str:
        return "foo"

    @staticmethod
    def false(settings: Settings, args: ExtArgs) -> str:
        return "foo"

    @staticmethod
    def does_not_exist(settings: Settings, args: ExtArgs) -> str:
        return "foo"

    PROGRAMS = (true, false, does_not_exist)


class TestSettingsSetProgramDefaults(TestCase):
    class DummySettingsObject(Settings):
        true: bool = True
        false: bool = True
        does_not_exist: bool = True

    def test_set_program_defaults(self) -> None:

        programs = DummyFormat.PROGRAMS
        dso = self.DummySettingsObject()
        dso._set_program_defaults(set(programs))

        names: List[str] = []
        for program in programs:
            names += [program.__func__.__name__]  # type: ignore

        self.assertTrue(getattr(dso, names[0]))
        self.assertTrue(getattr(dso, names[1]))
        self.assertFalse(getattr(dso, names[2]))
