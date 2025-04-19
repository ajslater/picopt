"""Archive Base Handler."""

from abc import ABC, abstractmethod
from collections.abc import Generator, Mapping
from datetime import datetime, timezone
from io import BytesIO
from operator import attrgetter
from pathlib import Path
from tarfile import TarFile, TarInfo
from types import MappingProxyType
from zipfile import ZipFile, ZipInfo

from py7zr import SevenZipFile
from py7zr.py7zr import FileInfo as SevenZipInfo
from rarfile import RarFile, RarInfo
from termcolor import cprint

from picopt.formats import FileFormat
from picopt.handlers.container import ContainerHandler
from picopt.handlers.non_pil import NonPILIdentifier
from picopt.path import PathInfo

_DATETIME_ATTRGETTER = attrgetter(
    "year", "month", "day", "hour", "minute", "second", "microsecond"
)


class ArchiveHandler(NonPILIdentifier, ContainerHandler, ABC):
    """Compressed Archive."""

    ARCHIVE_CLASS: type[ZipFile | TarFile | SevenZipFile | RarFile] = ZipFile
    ZIPINFO_MAP = MappingProxyType({})
    INFO_CLASS: type[ZipInfo | TarInfo | SevenZipInfo | RarInfo] = ZipInfo
    ARCHIVEINFO_MAP: MappingProxyType[
        type[ZipInfo | TarInfo | SevenZipInfo | RarInfo], Mapping[str, str]
    ] = MappingProxyType({})
    DTTM_ATTR = ""

    @classmethod
    @abstractmethod
    def _is_archive(cls, _path: Path | BytesIO) -> bool:
        raise NotImplementedError

    @classmethod
    def identify_format(cls, path_info: PathInfo) -> FileFormat | None:
        """Return the format if this handler can handle this path."""
        if cls._is_archive(path_info.path_or_buffer()):
            return super().identify_format(path_info)
        return None

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
    def _archive_infolist(archive):
        return archive.infolist()

    def _archive_readfile(self, archive, archiveinfo):
        return archive.read(archiveinfo)

    @classmethod
    def to_nativeinfo(cls, archive_info) -> ZipInfo | TarInfo | SevenZipInfo | RarInfo:
        """Convert other archive FileInfos to ZipInfo."""
        if isinstance(archive_info, cls.INFO_CLASS):
            return archive_info
        attr_map = cls.ARCHIVEINFO_MAP[type(archive_info)]
        native_kwargs = {}
        for native_attr, info_attr in attr_map.items():
            value = getattr(archive_info, info_attr, None)
            if value is None:
                continue
            if native_attr == cls.DTTM_ATTR and isinstance(value, int | float):
                value = datetime.fromtimestamp(value, tz=timezone.utc)
                value = _DATETIME_ATTRGETTER(value)
            native_kwargs[native_attr] = value
        return cls.INFO_CLASS(**native_kwargs)

    def unpack_into(self) -> Generator[PathInfo, None, None]:
        """Uncompress archive."""
        with self._get_archive() as archive:
            self._set_comment(archive)
            for archiveinfo in self._archive_infolist(archive):
                data = self._archive_readfile(archive, archiveinfo)
                if not data:
                    # Skip directories mostly.
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
            for path_info in tuple(self._optimized_contents):
                self._pack_info_one_file(archive, path_info)
                if self.config.verbose:
                    cprint(".", end="")
            if self.comment:
                archive.comment = self.comment
                if self.config.verbose:
                    cprint(".", end="")
        return output_buffer
