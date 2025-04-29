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

from picopt.archiveinfo import ArchiveInfo
from picopt.formats import FileFormat
from picopt.handlers.container import ContainerHandler, PackingContainerHandler
from picopt.handlers.non_pil import NonPILIdentifier
from picopt.path import PathInfo
from picopt.report import ReportStats


class ArchiveHandler(NonPILIdentifier, ContainerHandler, ABC):
    """Compressed Archive that must be converted with another handler."""

    INPUT_FORMAT_STR = "UNINMPLEMENTED"
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    ARCHIVE_CLASS: type[ZipFile | TarFile | SevenZipFile | RarFile] = ZipFile
    CONVERT_CHILDREN: bool = True
    CONTAINER_TYPE = "Archive"

    def __init__(self, *args, **kwargs):
        """Init Archive Treestamps."""
        super().__init__(*args, **kwargs)
        self._skip_path_infos = set()
        self._convert_children = self.CONVERT_CHILDREN and self.path_info.convert

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
            path_info=self.path_info,
            archiveinfo=archiveinfo,
            data=data,
            convert=self._convert_children,
            container_parents=self.path_info.container_path_history(),
        )

    def _is_archive_path_skip(self, path_info: PathInfo):
        return self._skipper and (
            self._skipper.is_walk_file_skip(path_info)
            or self._skipper.is_older_than_timestamp(path_info)
        )

    def _walk_one_entry(self, archive, archiveinfo) -> PathInfo | None:
        path_info = self._create_path_info(archiveinfo)
        if self._is_archive_path_skip(path_info):
            self._skip_path_infos.add(path_info)
            path_info = None
        elif data := self._archive_readfile(archive, archiveinfo):
            path_info.set_data(data)
        return path_info

    def _mark_delete(self, filename: str | Path) -> None:
        """NoOp for most archives."""

    def _consume_archive_timestamps(self, archive) -> tuple:
        infolist = self._archive_infolist(archive)
        if not (self.config.timestamps and self._timestamps):
            return infolist
        non_treestamp_entries = []
        timestamps_filename = self._timestamps.filename if self._timestamps else ""
        for archiveinfo in infolist:
            ai = ArchiveInfo(archiveinfo)
            if ai.is_dir():
                non_treestamp_entries.append(archiveinfo)
                continue
            path = Path(ai.filename())
            if path.name != timestamps_filename:
                non_treestamp_entries.append(archiveinfo)
                continue
            yaml_str = self._archive_readfile(archive, archiveinfo)
            archive_sub_path = self.path_info.archive_psuedo_path() / path.parent
            self._timestamps.loads(archive_sub_path, yaml_str)
            if self._skipper:
                self._printer.message_consumed_timestamp(path)
            self._mark_delete(path)

        return tuple(non_treestamp_entries)

    def _copy_unchanged_files(self, archive):
        """Copy unchanged paths into results."""
        while len(self._skip_path_infos):
            path_info = self._skip_path_infos.pop()
            archiveinfo = path_info.archiveinfo
            if archiveinfo and (
                data := self._archive_readfile(archive, archiveinfo.info)
            ):
                path_info.set_data(data)
            self.set_task(path_info, None)

    def walk(self) -> Generator[PathInfo]:
        """Walk an archive's archiveinfos."""
        self._printer.scan_archive(self.path_info)
        with self._get_archive() as archive:
            non_treestamp_entries = self._consume_archive_timestamps(archive)
            for archiveinfo in non_treestamp_entries:
                if path_info := self._walk_one_entry(archive, archiveinfo):
                    yield path_info
            if self._do_repack:
                self._copy_unchanged_files(archive)
        self._walk_finish()

    def _hydrate_optimized_path_info(self, path_info: PathInfo, report: ReportStats):
        """Rename archive files that changed."""
        super()._hydrate_optimized_path_info(path_info, report)
        original_path = path_info.name()
        final_path = report.path
        if final_path and original_path != final_path:
            path_info.rename(final_path)
            self._mark_delete(original_path)

    def optimize_contents(self):
        """Remove data structures that are no longer used."""
        super().optimize_contents()
        self._skip_path_infos = set()


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

    def _archive_write(self, archive):
        while self._optimized_contents:
            path_info = self._optimized_contents.pop()
            self._pack_info_one_file(archive, path_info)
            self._printer.packed_message()
        if self.comment:
            archive.comment = self.comment
            self._printer.packed_message()

    def pack_into(self) -> BytesIO:
        """Zip up the files in the tempdir into the new filename."""
        output_buffer = BytesIO()
        with self._archive_for_write(output_buffer) as archive:
            self._archive_write(archive)
        return output_buffer
