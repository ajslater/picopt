"""Test running external commands."""
from subprocess import CalledProcessError

from picopt import extern


__all__ = ()  # hides module from pydocstring


def test_extargs_class() -> None:
    eac = extern.ExtArgs("a", "b")
    assert type(eac) == extern.ExtArgs


def test_does_run_true() -> None:
    res = extern.does_external_program_run("true", 1)
    assert res


def test_does_run_garbage() -> None:
    res = extern.does_external_program_run("asdkfjadskl", 1)
    assert not res


def test_does_run_garbage_verbose() -> None:
    res = extern.does_external_program_run("asdkfjadskl", 2)
    assert not res


def test_run_ext_true() -> None:
    extern.run_ext(("true",))


def test_run_ext_bad() -> None:
    try:
        extern.run_ext(("false",))
    except CalledProcessError:
        pass
