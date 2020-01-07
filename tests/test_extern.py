"""Test running external commands."""
from unittest import TestCase

from picopt import extern


__all__ = ()  # hides module from pydocstring


class TestDoesExernalProgramRun(TestCase):
    def test_true(self) -> None:
        res = extern.does_external_program_run("true", True)
        self.assertTrue(res)

    def test_garbage(self) -> None:
        res = extern.does_external_program_run("asdkfjadskl", True)
        self.assertFalse(res)


class TestRunExt(TestCase):
    def test_true(self) -> None:
        extern.run_ext(("true",))
