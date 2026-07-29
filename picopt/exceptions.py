"""Picopt exceptions."""

import traceback


class PicoptError(Exception):
    """An exception specifically raised by picopt."""


class UnreadableImageError(PicoptError, OSError):
    """
    PIL identified an image format but could not parse the contents.

    Subclasses OSError because it wraps PIL's OSError and callers guard
    file handling with ``except OSError``.
    """


def print_exc_unless_expected(exc: BaseException) -> None:
    """
    Print a traceback only for unexpected exceptions.

    PicoptError subclasses are user-facing conditions already reported
    through warnings or error reports; a stack trace is noise for them.
    """
    if not isinstance(exc, PicoptError):
        traceback.print_exc()
