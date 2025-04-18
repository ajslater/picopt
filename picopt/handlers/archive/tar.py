"""TAR Handlers."""

from io import BytesIO
from pathlib import Path
from tarfile import REGTYPE, TarFile, TarInfo, is_tarfile
from tarfile import open as tar_open
from types import MappingProxyType
from zipfile import ZipFile

import filetype
from termcolor import cprint

from picopt.formats import FileFormat
from picopt.handlers.archive.archive import ArchiveHandler
from picopt.handlers.container import ContainerHandler


class Tar(ArchiveHandler):
    """Tarball Container."""

    INPUT_FORMAT_STR: str = "TAR"
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR: str = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR)
    PROGRAMS = ((ContainerHandler.INTERNAL,),)
    ARCHIVE_CLASS = TarFile
    ZIPINFO_MAP = MappingProxyType({"filename": "name", "date_time": "mtime"})
    COMPRESSION_MIME = ""
    WRITE_MODE = "w"
    COMPRESS_KWARGS = MappingProxyType({})

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

    def _set_comment(self, _archive: ZipFile) -> None:  # type: ignore[reportIncompatibleMethodOverride]
        """NoOp until inherit from ArchiveHandler."""

    @staticmethod
    def _archive_infolist(archive):
        return (tarinfo for tarinfo in archive.getmembers() if tarinfo.isfile())

    def _archive_readfile(self, archive, filename: str):
        return archive.extractfile(filename).read()

    def _archive_for_write(self, output_buffer: BytesIO) -> TarFile:
        return tar_open(
            mode=self.WRITE_MODE, fileobj=output_buffer, **self.COMPRESS_KWARGS
        )  # type: ignore[reportCallIssue]

    def _pack_info_one_file(self, archive, path_info):
        """Add one file to the new archive."""
        name = path_info.container_filename
        data = self._optimized_contents.pop(path_info)
        tarinfo = TarInfo(name=name)
        tarinfo.type = REGTYPE
        tarinfo.size = len(data)
        buf = BytesIO(data)
        archive.addfile(tarinfo, buf)
        if self.config.verbose:
            cprint(".", end="")


class TarGz(Tar):
    """GZipped Tarball Container."""

    INPUT_FORMAT_STR: str = "TGZ"
    SUFFIXES = (".tar.gz", ".tgz")
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR: str = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR)
    COMPRESSION_MIME = "application/gzip"
    WRITE_MODE = "w:gz"
    COMPRESS_KWARGS = MappingProxyType({"compresslevel": 9})


class TarBz(Tar):
    """BZipp2ed Tarball Container."""

    INPUT_FORMAT_STR: str = "TBZ"
    SUFFIXES = (".tar.bz2", ".tbz")
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR: str = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR)
    COMPRESSION_MIME = "application/x-bzip2"
    WRITE_MODE = "w:bz2"
    COMPRESS_KWARGS = MappingProxyType({"compresslevel": 9})


class TarXz(Tar):
    """LZMAed Tarball Container."""

    INPUT_FORMAT_STR: str = "TXZ"
    SUFFIXES = (".tar.xz", ".txz")
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR: str = INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR)
    COMPRESSION_MIME = "application/x-xz"
    WRITE_MODE = "w:xz"
    COMPRESS_KWARGS = MappingProxyType({"preset": 9})


class Cbt(Tar):
    """CBT Container."""

    INPUT_FORMAT_STR: str = "CBT"
    INPUT_SUFFIX: str = "." + INPUT_FORMAT_STR.lower()
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    # CBT is an abomination. Always convert to CBZ
    OUTPUT_FORMAT_STR: str = "CBZ"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)
