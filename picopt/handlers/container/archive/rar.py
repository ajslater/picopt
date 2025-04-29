"""RAR Handler."""

from io import BytesIO
from pathlib import Path

from rarfile import RarFile, RarInfo, is_rarfile

from picopt.formats import FileFormat
from picopt.handlers.container.archive import ArchiveHandler


class Rar(ArchiveHandler):
    """RAR Container."""

    INPUT_FORMAT_STR: str = "RAR"
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    # RAR is nonfree and often unable to repack with available tools. Always convert to Zip.
    PROGRAMS = (("unrar",),)
    ARCHIVE_CLASS = RarFile
    INFO_CLASS = RarInfo
    SUFFIXES = (".rar",)

    @classmethod
    def _is_archive(cls, path: Path | BytesIO) -> bool:
        return is_rarfile(path)

    @staticmethod
    def _archive_infolist(archive):
        return archive.infolist()

    def _archive_readfile(self, archive, archiveinfo):
        return archive.read(archiveinfo.filename)

    def _set_comment(self, archive: RarFile) -> None:  # type: ignore[reportIncompatibleMethodOverride]
        """Set the comment from the archive."""
        if archive.comment:
            self.comment = archive.comment.encode()


class Cbr(Rar):
    """CBR Container."""

    INPUT_FORMAT_STR: str = "CBR"
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    SUFFIXES = (".cbr",)
    # RAR is nonfree and often unable to repack with available tools. Always convert to CBZ.
