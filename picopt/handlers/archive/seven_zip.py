"""7Zip Handler."""

from io import BytesIO
from pathlib import Path
from sys import maxsize
from types import MappingProxyType

from py7zr import SevenZipFile, is_7zfile
from py7zr.io import BytesIOFactory

from picopt.formats import FileFormat
from picopt.handlers.archive.zip import Zip
from picopt.handlers.container import ContainerHandler


class SevenZip(Zip):
    """7Zip Container."""

    INPUT_FORMAT_STR: str = "7Z"
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    PROGRAMS = ((ContainerHandler.INTERNAL,),)
    ARCHIVE_CLASS = SevenZipFile
    ZIPINFO_MAP = MappingProxyType(
        {"filename": "filename", "date_time": "creationtime"}
    )

    def __init__(self, *args, **kwargs):
        """Add a py7zr factory for reading from RAM."""
        super().__init__(*args, **kwargs)
        self._factory = BytesIOFactory(maxsize)

    @classmethod
    def _is_archive(cls, path: Path | BytesIO) -> bool:
        return is_7zfile(path)

    @staticmethod
    def _archive_infolist(archive):
        return (archive.getinfo(name) for name in archive.namelist())

    def _archive_readfile(self, archive, filename):
        return archive.extract(targets=(filename,), factory=self._factory)


class Cb7(SevenZip):
    """CB7 Container."""

    INPUT_FORMAT_STR: str = "CB7"
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR: str = "CB7"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)
