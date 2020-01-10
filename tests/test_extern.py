"""Test running external commands."""
from subprocess import CalledProcessError
from unittest import TestCase

from picopt import extern


__all__ = ()  # hides module from pydocstring


def test_extargs_class():
    eac = extern.ExtArgs("a", "b")
    assert type(eac) == extern.ExtArgs


class TestDoesExernalProgramRun(TestCase):
    def test_true(self) -> None:
        res = extern.does_external_program_run("true", 1)
        self.assertTrue(res)

    def test_garbage(self) -> None:
        res = extern.does_external_program_run("asdkfjadskl", 1)
        self.assertFalse(res)

    def test_garbage_verbose(self) -> None:
        res = extern.does_external_program_run("asdkfjadskl", 2)
        self.assertFalse(res)


class TestRunExt(TestCase):
    def test_true(self) -> None:
        extern.run_ext(("true",))

    def test_bad(self) -> None:
        try:
            extern.run_ext(("false",))
        except CalledProcessError:
            pass
