"""Picopt init and module constants."""

from os import environ

PROGRAM_NAME = "picopt"
WORKING_SUFFIX: str = f".{PROGRAM_NAME}-tmp"

if environ.get("PYTHONDEVMODE"):
    from icecream import install  # pyright: ignore[reportPrivateImportUsage]

    install()
