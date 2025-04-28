"""7Zip Handler."""

from io import BytesIO
from pathlib import Path
from sys import maxsize

from py7zr import SevenZipFile, is_7zfile
from py7zr.io import BytesIOFactory
from py7zr.py7zr import FileInfo as SevenZipInfo

from picopt.formats import FileFormat
from picopt.handlers.container.archive import PackingArchiveHandler
from picopt.handlers.handler import INTERNAL


class SevenZip(PackingArchiveHandler):
    """7Zip Container."""

    INPUT_FORMAT_STR: str = "7Z"
    SUFFIXES = (".7z",)
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = INPUT_FILE_FORMAT
    PROGRAMS = ((INTERNAL,),)
    ARCHIVE_CLASS = SevenZipFile
    INFO_CLASS = SevenZipInfo

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

    def _archive_for_write(self, output_buffer: BytesIO):
        # w flushes the writes on close. x does not.
        # https://github.com/miurahr/py7zr/blob/b05ef454e65db9fa1d2da03378c915df913bf89d/py7zr/py7zr.py#L1152
        # It seems onerous with py7zr to extract the compression filters used to make
        # the archive, so remembering it will not be supported until py7zr makes it easy.
        return SevenZipFile(output_buffer, mode="w")

    def _pack_info_one_file(self, archive, path_info):
        """Add one file to the new archive."""
        data = BytesIO(path_info.data())
        arcname = path_info.archiveinfo.filename()
        archive.writef(data, arcname=arcname)


class Cb7(SevenZip):
    """CB7 Container."""

    INPUT_FORMAT_STR: str = "CB7"
    SUFFIXES = (".cb7",)
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = INPUT_FILE_FORMAT
