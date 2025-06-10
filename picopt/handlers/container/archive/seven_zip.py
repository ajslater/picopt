"""7Zip Handler."""

from io import BytesIO
from pathlib import Path
from sys import maxsize

from py7zr import SevenZipFile, is_7zfile
from py7zr.io import BytesIOFactory
from py7zr.py7zr import FileInfo as SevenZipInfo
from typing_extensions import override

from picopt.formats import FileFormat
from picopt.handlers.container.archive import (
    ArchiveClassType,
    ArchiveInfoClassType,
    PackingArchiveHandler,
)
from picopt.handlers.handler import INTERNAL


class SevenZip(PackingArchiveHandler):
    """7Zip Container."""

    INPUT_FORMAT_STR: str = "7Z"
    SUFFIXES: tuple[str, ...] = (".7z",)
    INPUT_FILE_FORMAT: FileFormat = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR: str = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT: FileFormat = INPUT_FILE_FORMAT
    PROGRAMS: tuple[tuple[str, ...], ...] = ((INTERNAL,),)
    ARCHIVE_CLASS: ArchiveClassType = SevenZipFile
    INFO_CLASS: ArchiveInfoClassType = SevenZipInfo

    def __init__(self, *args, **kwargs):
        """Add a py7zr factory for reading from RAM."""
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
    def _archive_readfile(self, archive, archiveinfo):
        """Read file into memory."""
        sevenzipinfo = archiveinfo
        if sevenzipinfo.is_directory:
            return b""
        filename = sevenzipinfo.filename
        archive.reset()
        archive.extract(targets=[filename], factory=self._factory)
        data = self._factory.products.get(filename)
        if not data:
            return data
        return data.read()

    @override
    def _archive_for_write(self, output_buffer: BytesIO):
        # It seems onerous with py7zr to extract the compression filters used to make
        # the archive, so remembering it will not be supported until py7zr makes it easy.
        return SevenZipFile(output_buffer, mode="x")

    @override
    def _pack_info_one_file(self, archive, path_info):
        """Add one file to the new archive."""
        data = BytesIO(path_info.data())
        arcname = path_info.archiveinfo.filename()
        archive.writef(data, arcname=arcname)


class Cb7(SevenZip):
    """CB7 Container."""

    INPUT_FORMAT_STR: str = "CB7"
    SUFFIXES: tuple[str, ...] = (".cb7",)
    INPUT_FILE_FORMAT: FileFormat = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR: str = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT: FileFormat = INPUT_FILE_FORMAT
