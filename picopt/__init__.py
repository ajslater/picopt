"""Picopt init and module constants."""

from functools import cache
from importlib.metadata import PackageNotFoundError, version
from os import environ

PROGRAM_NAME = "picopt"
WORKING_SUFFIX: str = f".{PROGRAM_NAME}-tmp"


@cache
def get_version() -> str:
    """Return the installed picopt version."""
    try:
        return version(PROGRAM_NAME)
    except PackageNotFoundError:
        return "test"


if environ.get("PYTHONDEVMODE"):
    from icecream import install  # pyright: ignore[reportPrivateImportUsage]

    install()
