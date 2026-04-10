"""
7-Zip archive plugin.

Owns: SevenZip, Cb7. Uses py7zr for both reading and writing. py7zr is a
pure-Python (with C accelerators) library, so the "tool" here is an
:class:`InternalTool` and its presence is governed by whether py7zr is
installed.
"""

from __future__ import annotations

from io import BytesIO
from sys import maxsize
from typing import TYPE_CHECKING

from py7zr import SevenZipFile, is_7zfile
from py7zr.io import BytesIOFactory
from typing_extensions import override

from picopt.formats import FileFormat
from picopt.plugins.base import (
    ArchiveHandler,
    Detector,
    Handler,
    InternalTool,
    Plugin,
    Route,
    Tool,
)

if TYPE_CHECKING:
    from pathlib import Path

    from picopt.path import PathInfo


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


class Py7zrTool(InternalTool):
    """The py7zr Python library."""

    name = "py7zr"
    module_name = "py7zr"

    @override
    def run_pack(self, handler: Handler) -> BytesIO:
        if not isinstance(handler, SevenZip):
            msg = "Py7zrTool only packs SevenZip handlers"
            raise TypeError(msg)
        return ArchiveHandler.pack_into(handler)


_PY7ZR_TOOL = Py7zrTool()


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class SevenZipDetector(Detector):
    """Detect ``.7z`` and ``.cb7``."""

    PRIORITY: int = 10

    @override
    @classmethod
    def identify(cls, path_info: PathInfo) -> FileFormat | None:
        suffix = path_info.suffix().lower()
        if suffix not in _SUFFIX_TO_FORMAT:
            return None
        if not is_7zfile(path_info.path_or_buffer()):
            return None
        return _SUFFIX_TO_FORMAT[suffix]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class SevenZip(ArchiveHandler):
    """
    7-Zip container.

    py7zr requires extracting through a factory rather than reading entries
    one at a time, so this handler keeps a per-instance
    :class:`BytesIOFactory` and asks py7zr to materialize each requested
    entry into it on demand.
    """

    OUTPUT_FORMAT_STR: str = "7Z"
    SUFFIXES: tuple[str, ...] = (".7z",)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    ARCHIVE_CLASS = SevenZipFile
    PIPELINE: tuple[tuple[Tool, ...], ...] = ((_PY7ZR_TOOL,),)

    def __init__(self, *args, **kwargs) -> None:
        """Allocate the py7zr extraction factory."""
        super().__init__(*args, **kwargs)
        self._factory: BytesIOFactory = BytesIOFactory(maxsize)

    @override
    @classmethod
    def _is_archive(cls, path: Path | BytesIO) -> bool:
        return is_7zfile(path)

    @override
    @staticmethod
    def _archive_infolist(archive):
        return archive.list()

    @override
    def _archive_readfile(self, archive, archiveinfo) -> bytes:
        if archiveinfo.is_directory:
            return b""
        filename = archiveinfo.filename
        archive.reset()
        archive.extract(targets=[filename], factory=self._factory)
        if not (data := self._factory.products.get(filename)):
            return b""
        return data.read()

    @override
    def _archive_for_write(self, output_buffer: BytesIO) -> SevenZipFile:
        # py7zr does not expose the original archive's compression filters
        # in a way we can round-trip cleanly, so new archives use py7zr's
        # default LZMA2 settings.
        return SevenZipFile(output_buffer, mode="x")

    @override
    def _pack_info_one_file(self, archive, path_info) -> None:
        data = BytesIO(path_info.data())
        arcname = path_info.archiveinfo.filename()
        archive.writef(data, arcname=arcname)


class Cb7(SevenZip):
    """CB7 comic-book 7-zip archive."""

    OUTPUT_FORMAT_STR: str = "CB7"
    SUFFIXES: tuple[str, ...] = (".cb7",)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})


_SUFFIX_TO_FORMAT: dict[str, FileFormat] = {
    ".7z": SevenZip.OUTPUT_FILE_FORMAT,
    ".cb7": Cb7.OUTPUT_FILE_FORMAT,
}


PLUGIN = Plugin(
    name="7Z",
    handlers=(SevenZip, Cb7),
    routes=(
        Route(file_format=SevenZip.OUTPUT_FILE_FORMAT, native=SevenZip),
        Route(file_format=Cb7.OUTPUT_FILE_FORMAT, native=Cb7),
    ),
    detector=SevenZipDetector,
    default_enabled=False,
)
