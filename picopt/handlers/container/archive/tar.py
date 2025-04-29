"""TAR Handlers."""

from io import BytesIO
from pathlib import Path
from tarfile import TarFile, TarInfo, is_tarfile
from tarfile import open as tar_open
from types import MappingProxyType

import filetype

from picopt.formats import FileFormat
from picopt.handlers.container.archive import PackingArchiveHandler
from picopt.handlers.handler import INTERNAL


class Tar(PackingArchiveHandler):
    """Tarball Container."""

    INPUT_FORMAT_STR: str = "TAR"
    SUFFIXES = (".tar",)
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR: str = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    PROGRAMS = ((INTERNAL,),)
    ARCHIVE_CLASS = TarFile
    INFO_CLASS = TarInfo
    WRITE_MODE = "w"
    COMPRESS_KWARGS = MappingProxyType({})
    COMPRESSION_MIME = ""

    @classmethod
    def _is_archive(cls, path: Path | BytesIO) -> bool:
        result = is_tarfile(path)
        if result and cls.COMPRESSION_MIME:
            ft = filetype.guess(path)
            result = bool(ft) and ft.mime == cls.COMPRESSION_MIME
        return result

    def _get_archive(self):  # type: ignore[reportIncompatibleMethodOverride]
        """Use the handler's archive class for this archive."""
        archive = tar_open(self.original_path, "r")  # noqa: SIM115, type: ignore[reportArgumentType]
        if not archive:
            msg = f"Unknown archive type: {self.original_path}"
            raise ValueError(msg)
        return archive

    def _set_comment(self, archive: TarFile) -> None:  # type: ignore[reportIncompatibleMethodOverride]
        """NoOp until inherit from ArchiveHandler."""

    @staticmethod
    def _archive_infolist(archive):
        return archive.getmembers()

    def _archive_readfile(self, archive, archiveinfo):
        if buf := archive.extractfile(archiveinfo):
            return buf.read()
        return b""

    def _archive_for_write(self, output_buffer: BytesIO) -> TarFile:
        return tar_open(
            mode=self.WRITE_MODE, fileobj=output_buffer, **self.COMPRESS_KWARGS
        )  # type: ignore[reportCallIssue]

    def _pack_info_one_file(self, archive, path_info):
        """Add one file to the new archive."""
        tarinfo = path_info.archiveinfo.to_tarinfo()
        data = path_info.data()
        tarinfo.size = len(data)
        buf = BytesIO(data)
        archive.addfile(tarinfo, buf)


class TarGz(Tar):
    """GZipped Tarball Container."""

    INPUT_FORMAT_STR = "TGZ"
    SUFFIXES = (".tar.gz", ".tgz")
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    COMPRESSION_MIME = "application/gzip"
    WRITE_MODE = "w:gz"
    COMPRESS_KWARGS = MappingProxyType({"compresslevel": 9})


class TarBz(Tar):
    """BZipp2ed Tarball Container."""

    INPUT_FORMAT_STR = "TBZ"
    SUFFIXES = (".tar.bz2", ".tbz")
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    COMPRESSION_MIME = "application/x-bzip2"
    WRITE_MODE = "w:bz2"
    COMPRESS_KWARGS = MappingProxyType({"compresslevel": 9})


class TarXz(Tar):
    """LZMAed Tarball Container."""

    INPUT_FORMAT_STR = "TXZ"
    SUFFIXES = (".tar.xz", ".txz")
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    COMPRESSION_MIME = "application/x-xz"
    WRITE_MODE = "w:xz"
    COMPRESS_KWARGS = MappingProxyType({"preset": 9})


class Cbt(Tar):
    """CBT Container."""

    INPUT_FORMAT_STR = "CBT"
    SUFFIXES = (".cbt",)
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
