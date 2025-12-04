"""Picopt init and module constants."""

from os import environ

PROGRAM_NAME = "picopt"

if environ.get("PYTHONDEVMODE"):
    from icecream import install  # pyright: ignore[reportPrivateImportUsage]

    install()
