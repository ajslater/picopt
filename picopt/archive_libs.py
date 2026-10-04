"""
The core's only imports of the archive format libraries.

picopt's core names py7zr's ``FileInfo`` and rarfile's ``RarInfo`` in
annotations and match patterns, and every handler imports that core. If the
core imported the libraries directly, a broken py7zr or rarfile would stop
every run, even a JPEG-only one. Importing them here instead, with a
placeholder for a library that fails to import, leaves the failure to the
format's own plugin, which the registry then disables on its own.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

__all__ = ("RarInfo", "SevenZipInfo")


def _import_class(module_name: str, class_name: str) -> type:
    """Return the library's class, or a placeholder if it can't import."""
    try:
        module = import_module(module_name)
    except ImportError:
        # Nothing is an instance of a fresh class, so isinstance checks and
        # match patterns against it never match. That is correct: no member
        # of this kind can exist without its library. The plugin that needs
        # the library re-raises the same ImportError and is disabled.
        return type(class_name, (), {"__module__": __name__})
    return getattr(module, class_name)


if TYPE_CHECKING:
    # Type checkers see only the real classes, so ArchiveInfoType stays
    # closed and the assert_never matches keep checking exhaustively.
    from py7zr.py7zr import FileInfo as SevenZipInfo
    from rarfile import RarInfo
else:
    SevenZipInfo = _import_class("py7zr.py7zr", "FileInfo")
    RarInfo = _import_class("rarfile", "RarInfo")
