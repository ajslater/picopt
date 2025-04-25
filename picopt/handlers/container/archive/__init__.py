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
from treestamps import Grovestamps

from picopt.archiveinfo import ArchiveInfo
from picopt.formats import FileFormat
from picopt.handlers.container import ContainerHandler, PackingContainerHandler
from picopt.handlers.non_pil import NonPILIdentifier
from picopt.path import PathInfo
from picopt.walk.skip import WalkSkipper


class ArchiveHandler(NonPILIdentifier, ContainerHandler, ABC):
    """Compressed Archive that must be converted with another handler."""

    INPUT_FORMAT_STR = "UNINMPLEMENTED"
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    ARCHIVE_CLASS: type[ZipFile | TarFile | SevenZipFile | RarFile] = ZipFile
    CONVERT_CHILDREN: bool = True

    def __init__(
        self,
        *args,
        timestamps: Grovestamps | None = None,
        **kwargs,
    ):
        """Init Archive Treestamps."""
        super().__init__(*args, **kwargs)
        self._timestamps = timestamps
        self._skipper = WalkSkipper(self.config, timestamps)

    @classmethod
    @abstractmethod
    def _is_archive(cls, _path: Path | BytesIO) -> bool:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def _archive_infolist(archive):
        raise NotImplementedError

    @abstractmethod
    def _archive_readfile(self, archive, archiveinfo):
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

    def _create_path_info(self, archiveinfo, data: bytes | None = None):
        return PathInfo(
            self.path_info.top_path,
            self.CONVERT_CHILDREN and self.path_info.convert,
            archiveinfo=archiveinfo,
            data=data,
            container_parents=self.path_info.container_path_history(),
            is_case_sensitive=self.path_info.is_case_sensitive,
        )

    def _is_archive_path_skip(self, path_info: PathInfo):
        return self._skipper.is_walk_file_skip(
            path_info
        ) or self._skipper.is_older_than_timestamp(path_info)

    def _walk_one_entry(self, archive, archiveinfo) -> tuple[PathInfo, bool]:
        path_info = self._create_path_info(archiveinfo)
        skip = self._is_archive_path_skip(path_info)
        if not skip and (data := self._archive_readfile(archive, archiveinfo)):
            path_info.set_data(data)
        return path_info, skip

    def _consume_archive_timestamps(self, archive) -> tuple:
        non_treestamp_entries = []
        timestamps_filename = self._timestamps.filename if self._timestamps else ""
        for archiveinfo in self._archive_infolist(archive):
            add = True
            if self.config.timestamps and self._timestamps:
                ai = ArchiveInfo(archiveinfo)
                if not ai.is_dir():
                    path = Path(ai.filename())
                    if path.name == timestamps_filename:
                        yaml_str = self._archive_readfile(archive, archiveinfo)
                        archive_sub_path = (
                            self.path_info.archive_psuedo_path() / path.parent
                        )
                        self._timestamps.loads(archive_sub_path, yaml_str)
                        add = False
            if add:
                non_treestamp_entries.append(archiveinfo)

        return tuple(non_treestamp_entries)

    def walk(self) -> Generator[tuple[PathInfo, bool]]:
        """Walk an archive's archiveinfos."""
        if self.config.verbose > 1:
            cprint(f"\nScanning archive {self.path_info.full_output_name()}...", end="")
        with self._get_archive() as archive:
            non_treestamp_entries = self._consume_archive_timestamps(archive)
            for archiveinfo in non_treestamp_entries:
                yield self._walk_one_entry(archive, archiveinfo)

    def copy_skipped_files(self, skipped_paths: list[PathInfo]):
        """Reopen the archive for skipped paths."""
        with self._get_archive() as archive:
            for path_info in skipped_paths:
                archiveinfo = path_info.archiveinfo
                if archiveinfo and (
                    data := self._archive_readfile(archive, archiveinfo.info)
                ):
                    path_info.set_data(data)
                self.set_task(path_info, None)
                if self.config.verbose:
                    cprint(".", attrs=["dark"], end="")


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
