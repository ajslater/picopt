"""RAR Handler."""

from io import BytesIO
from pathlib import Path

from rarfile import RarFile, RarInfo, is_rarfile
from typing_extensions import override

from picopt.formats import FileFormat
from picopt.handlers.container.archive import (
    ArchiveClassType,
    ArchiveHandler,
    ArchiveInfoClassType,
)


class Rar(ArchiveHandler):
    """
    RAR Container.

    RAR is nonfree and often unable to repack with available tools. Always convert to Zip.
    """

    INPUT_FORMAT_STR: str = "RAR"
    INPUT_FILE_FORMAT: FileFormat = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset({INPUT_FILE_FORMAT})
    PROGRAMS: tuple[tuple[str, ...]] = (("unrar",),)
    ARCHIVE_CLASS: ArchiveClassType = RarFile
    INFO_CLASS: ArchiveInfoClassType = RarInfo
    SUFFIXES: tuple[str, ...] = (".rar",)

    @override
    @classmethod
    def _is_archive(cls, path: Path | BytesIO) -> bool:
        return is_rarfile(path)

    @override
    @staticmethod
    def _archive_infolist(archive):
        return archive.infolist()

    @override
    def _archive_readfile(self, archive, archiveinfo):
        if archiveinfo.is_dir():
            # Rarfile empty directories throw
            return b""
        return archive.read(archiveinfo.filename)

    @override
    def _set_comment(self, archive: RarFile) -> None:  # type: ignore[reportIncompatibleMethodOverride]
        """Set the comment from the archive."""
        if archive.comment:
            self.comment: bytes | None = archive.comment.encode()


class Cbr(Rar):
    """
    CBR Container.

    RAR is nonfree and often unable to repack with available tools. Always convert to CBZ.
    """

    INPUT_FORMAT_STR: str = "CBR"
    INPUT_FILE_FORMAT: FileFormat = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset({INPUT_FILE_FORMAT})
    SUFFIXES: tuple[str, ...] = (".cbr",)
