"""TAR Handlers."""

from io import BytesIO
from pathlib import Path
from tarfile import TarFile, TarInfo, is_tarfile
from tarfile import open as tar_open
from types import MappingProxyType
from typing import Any

import filetype
from typing_extensions import override

from picopt.formats import FileFormat
from picopt.handlers.container.archive import (
    ArchiveClassType,
    ArchiveInfoClassType,
    PackingArchiveHandler,
)
from picopt.handlers.handler import INTERNAL


class Tar(PackingArchiveHandler):
    """Tarball Container."""

    INPUT_FORMAT_STR: str = "TAR"
    SUFFIXES: tuple[str, ...] = (".tar",)
    INPUT_FILE_FORMAT: FileFormat = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR: str = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    PROGRAMS: tuple[tuple[str, ...], ...] = ((INTERNAL,),)
    ARCHIVE_CLASS: ArchiveClassType = TarFile
    INFO_CLASS: ArchiveInfoClassType = TarInfo
    WRITE_MODE: str = "w"
    COMPRESS_KWARGS: MappingProxyType[str, Any] = MappingProxyType({})
    COMPRESSION_MIME: str = ""

    @override
    @classmethod
    def _is_archive(cls, path: Path | BytesIO) -> bool:
        result = is_tarfile(path)
        if result and cls.COMPRESSION_MIME:
            ft = filetype.guess(path)
            result = bool(ft) and ft.mime == cls.COMPRESSION_MIME
        return result

    @override
    def _get_archive(self):
        """Use the handler's archive class for this archive."""
        archive = tar_open(self.original_path, "r")  # noqa: SIM115
        if not archive:
            msg = f"Unknown archive type: {self.original_path}"
            raise ValueError(msg)
        return archive

    @override
    def _set_comment(self, archive: TarFile) -> None:
        """NoOp until inherit from ArchiveHandler."""

    @override
    @staticmethod
    def _archive_infolist(archive):
        return archive.getmembers()

    @override
    def _archive_readfile(self, archive, archiveinfo):
        if buf := archive.extractfile(archiveinfo):
            return buf.read()
        return b""

    @override
    def _archive_for_write(self, output_buffer: BytesIO) -> TarFile:
        return tar_open(  # pyright: ignore[reportCallIssue]
            mode=self.WRITE_MODE,  # pyright: ignore[reportArgumentType]
            fileobj=output_buffer,
            **self.COMPRESS_KWARGS,
        )

    @override
    def _pack_info_one_file(self, archive, path_info):
        """Add one file to the new archive."""
        tarinfo = path_info.archiveinfo.to_tarinfo()
        data = path_info.data()
        tarinfo.size = len(data)
        buf = BytesIO(data)
        archive.addfile(tarinfo, buf)


class TarGz(Tar):
    """GZipped Tarball Container."""

    INPUT_FORMAT_STR: str = "TGZ"
    SUFFIXES: tuple[str, ...] = (".tar.gz", ".tgz")
    INPUT_FILE_FORMAT: FileFormat = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR: str = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    COMPRESSION_MIME: str = "application/gzip"
    WRITE_MODE: str = "w:gz"
    COMPRESS_KWARGS: MappingProxyType[str, Any] = MappingProxyType({"compresslevel": 9})


class TarBz(Tar):
    """BZipp2ed Tarball Container."""

    INPUT_FORMAT_STR: str = "TBZ"
    SUFFIXES: tuple[str, ...] = (".tar.bz2", ".tbz")
    INPUT_FILE_FORMAT: FileFormat = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR: str = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    COMPRESSION_MIME: str = "application/x-bzip2"
    WRITE_MODE: str = "w:bz2"
    COMPRESS_KWARGS: MappingProxyType[str, Any] = MappingProxyType({"compresslevel": 9})


class TarXz(Tar):
    """LZMAed Tarball Container."""

    INPUT_FORMAT_STR: str = "TXZ"
    SUFFIXES: tuple[str, ...] = (".tar.xz", ".txz")
    INPUT_FILE_FORMAT: FileFormat = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR: str = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    COMPRESSION_MIME: str = "application/x-xz"
    WRITE_MODE: str = "w:xz"
    COMPRESS_KWARGS: MappingProxyType[str, Any] = MappingProxyType({"preset": 9})


class Cbt(Tar):
    """CBT Container."""

    INPUT_FORMAT_STR: str = "CBT"
    SUFFIXES: tuple[str, ...] = (".cbt",)
    INPUT_FILE_FORMAT: FileFormat = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset({INPUT_FILE_FORMAT})
