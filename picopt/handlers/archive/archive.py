"""Archive Base Handler."""

from abc import ABC, abstractmethod
from collections.abc import Generator
from io import BytesIO
from pathlib import Path
from tarfile import TarFile, TarInfo
from zipfile import ZipFile, ZipInfo

from py7zr import SevenZipFile
from py7zr.py7zr import FileInfo as SevenZipInfo
from rarfile import RarFile, RarInfo
from termcolor import cprint

from picopt.formats import FileFormat
from picopt.handlers.container import ContainerHandler, PackingContainerHandler
from picopt.handlers.non_pil import NonPILIdentifier
from picopt.path import PathInfo


class ArchiveHandler(NonPILIdentifier, ContainerHandler, ABC):
    """Compressed Archive that must be converted with another handler."""

    ARCHIVE_CLASS: type[ZipFile | TarFile | SevenZipFile | RarFile] = ZipFile
    INPUT_FORMAT_STR = "Unimplemented"
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    SUFFIXES = ()

    @classmethod
    @abstractmethod
    def _is_archive(cls, _path: Path | BytesIO) -> bool:
        raise NotImplementedError

    @classmethod
    def identify_format(cls, path_info: PathInfo) -> FileFormat | None:
        """Return the format if this handler can handle this path."""
        fmt = None
        if cls._is_archive(path_info.path_or_buffer()):
            fmt = super().identify_format(path_info)
        return fmt

    def _get_archive(self):
        """Use the handler's archive class for this archive."""
        archive = self.ARCHIVE_CLASS(self.original_path, "r")
        if not archive:
            msg = f"Unknown archive type: {self.original_path}"
            raise ValueError(msg)
        return archive

    def _set_comment(self, archive) -> None:
        """NoOp for many archive formats."""

    @staticmethod
    @abstractmethod
    def _archive_infolist(archive):
        raise NotImplementedError

    @abstractmethod
    def _archive_readfile(self, archive, archiveinfo):
        raise NotImplementedError

    def unpack_into(self) -> Generator[PathInfo, None, None]:
        """Uncompress archive."""
        with self._get_archive() as archive:
            self._set_comment(archive)
            for archiveinfo in self._archive_infolist(archive):
                data = self._archive_readfile(archive, archiveinfo)
                if data is None:
                    continue
                path_info = PathInfo(
                    self.path_info.top_path,  # Change this when i do internal times?
                    self.path_info.mtime(),  # Change this when I do internal times.
                    self.path_info.convert,
                    self.path_info.is_case_sensitive,
                    archiveinfo=archiveinfo,
                    data=data,
                    container_paths=self.get_container_paths(),
                )
                yield path_info
                if self.config.verbose:
                    cprint(".", end="")


class PackingArchiveHandler(ArchiveHandler, PackingContainerHandler, ABC):
    """Compressed Archive."""

    OUTPUT_FORMAT_STR = ArchiveHandler.INPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR)
    INFO_CLASS: type[ZipInfo | TarInfo | SevenZipInfo | RarInfo] = ZipInfo

    @abstractmethod
    def _archive_for_write(self, output_buffer: BytesIO):
        raise NotImplementedError

    @abstractmethod
    def _pack_info_one_file(self, archive, path_info):
        raise NotImplementedError

    def pack_into(self) -> BytesIO:
        """Zip up the files in the tempdir into the new filename."""
        output_buffer = BytesIO()
        archive = self._archive_for_write(output_buffer)
        with archive:
            for path_info in tuple(self.optimized_contents):
                self._pack_info_one_file(archive, path_info)
                if self.config.verbose:
                    cprint(".", end="")
            if self.comment:
                archive.comment = self.comment
                if self.config.verbose:
                    cprint(".", end="")
        return output_buffer
