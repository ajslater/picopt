"""7Zip Handler."""

from io import BytesIO
from pathlib import Path
from sys import maxsize
from tarfile import TarInfo
from types import MappingProxyType
from zipfile import ZipInfo

from py7zr import SevenZipFile, is_7zfile
from py7zr.io import BytesIOFactory
from py7zr.py7zr import FileInfo as SevenZipInfo
from rarfile import RarInfo

from picopt.formats import FileFormat
from picopt.handlers.archive.archive import ArchiveHandler
from picopt.handlers.container import ContainerHandler


class SevenZip(ArchiveHandler):
    """7Zip Container."""

    INPUT_FORMAT_STR: str = "7Z"
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = INPUT_FILE_FORMAT
    PROGRAMS = ((ContainerHandler.INTERNAL,),)
    ARCHIVE_CLASS = SevenZipFile
    INFO_CLASS = SevenZipInfo
    ARHIVEINFO_MAP = MappingProxyType(
        {
            RarInfo: {"filename": "filename", "creationtime": "date_time"},
            TarInfo: {"filename": "name", "creationtime": "mtime"},
            ZipInfo: {"filename": "filename", "creationtime": "date_time"},
        }
    )
    DTTM_ATTR = "creationtime"

    def __init__(self, *args, **kwargs):
        """Add a py7zr factory for reading from RAM."""
        super().__init__(*args, **kwargs)
        self._factory = BytesIOFactory(maxsize)

    @classmethod
    def _is_archive(cls, path: Path | BytesIO) -> bool:
        return is_7zfile(path)

    @staticmethod
    def _archive_infolist(archive):
        return archive.list()

    def _archive_readfile(self, archive, archiveinfo):
        """Read file into memory."""
        if archiveinfo.is_directory:
            return None
        filename = archiveinfo.filename
        archive.reset()
        archive.extract(targets=[filename], factory=self._factory)
        data = self._factory.products.get(filename)
        if not data:
            return data
        return data.read()

    def _archive_for_write(self, output_buffer: BytesIO):
        # w flushes the writes on close. x does not.
        # https://github.com/miurahr/py7zr/blob/b05ef454e65db9fa1d2da03378c915df913bf89d/py7zr/py7zr.py#L1152
        return SevenZipFile(output_buffer, mode="w")

    def _pack_info_one_file(self, archive, path_info):
        """Add one file to the new archive."""
        filename = path_info.container_filename
        data = self._optimized_contents.pop(path_info)
        archive.writef(BytesIO(data), arcname=filename)


class Cb7(SevenZip):
    """CB7 Container."""

    INPUT_FORMAT_STR: str = "CB7"
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = INPUT_FILE_FORMAT
