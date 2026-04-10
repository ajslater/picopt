"""Archive container handler base."""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

from typing_extensions import override

from picopt.archiveinfo import ArchiveInfo
from picopt.path import PathInfo
from picopt.plugins.base.container import ContainerHandler
from picopt.plugins.base.handler import Handler

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from picopt.formats import FileFormat
    from picopt.report import ReportStats


class ArchiveHandler(ContainerHandler, ABC):
    """
    Compressed archive container.

    Subclasses provide:
        - ``ARCHIVE_CLASS``: e.g. ``ZipFile``, ``TarFile``, ``SevenZipFile``.
        - ``_is_archive(path)``: classmethod sniff.
        - ``_archive_infolist(archive)``: list of entries.
        - ``_archive_readfile(archive, archiveinfo)``: bytes for one entry.
        - For packing archives only: ``_archive_for_write`` and
          ``_pack_info_one_file``.
    """

    CONTAINER_TYPE: str = "Archive"
    CONVERT_CHILDREN: bool = True
    ARCHIVE_CLASS: type[Any]

    def __init__(self, *args, **kwargs) -> None:
        """Init archive variables."""
        super().__init__(*args, **kwargs)
        self._skip_path_infos: set[PathInfo] = set()
        self._convert_children = self.CONVERT_CHILDREN and self.path_info.convert

    # ------------------------------------------------------------ sniffing

    @classmethod
    @abstractmethod
    def _is_archive(cls, path: Path | BytesIO) -> bool:
        """Return True if the bytes/path look like this archive type."""

    # ------------------------------------------------------------- reading

    @staticmethod
    @abstractmethod
    def _archive_infolist(archive) -> Iterable:
        """Return the list of entries in the open archive."""

    @abstractmethod
    def _archive_readfile(self, archive, archiveinfo) -> bytes:
        """Read the data for one archive entry."""

    def _get_archive(self):
        """Open the archive for reading."""
        archive_class = type(self).ARCHIVE_CLASS
        archive = archive_class(self.original_path, "r")
        if not archive:
            msg = f"Unknown archive type: {self.original_path}"
            raise ValueError(msg)
        return archive

    def _set_comment(self, archive) -> None:
        """Default: no comment support."""

    # ----------------------------------------------------------- packing

    def _archive_for_write(self, output_buffer: BytesIO):
        """Open the archive for writing; CAN_PACK handlers must override."""
        msg = f"{type(self).__name__} does not support packing"
        raise NotImplementedError(msg)

    def _pack_info_one_file(self, archive, path_info) -> None:
        """Add one file to the new archive; CAN_PACK handlers must override."""
        msg = f"{type(self).__name__} does not support packing"
        raise NotImplementedError(msg)

    def _archive_write(self, archive) -> None:
        while self._optimized_contents:
            path_info = self._optimized_contents.pop()
            self._pack_info_one_file(archive, path_info)
            self._printer.packed()
        if self.comment:
            archive.comment = self.comment
            self._printer.packed()

    @override
    def pack_into(self) -> BytesIO:
        """Pack into a BytesIO and return it."""
        if not self.CAN_PACK:
            msg = f"{type(self).__name__} is a read-only archive."
            raise NotImplementedError(msg)
        output_buffer = BytesIO()
        with self._archive_for_write(output_buffer) as archive:
            self._archive_write(archive)
        return output_buffer

    # ------------------------------------------------------------ identify

    @override
    @classmethod
    def identify_format(cls, path_info: PathInfo) -> FileFormat | None:
        """Sniff the file then fall back to suffix-based default."""
        if cls._is_archive(path_info.path_or_buffer()):
            return Handler.identify_format.__func__(cls, path_info)
        return None

    # --------------------------------------------------------------- walk

    def _create_path_info(self, archiveinfo, data: bytes | None = None):

        return PathInfo(
            path_info=self.path_info,
            archiveinfo=archiveinfo,
            data=data,
            convert=self._convert_children,
            container_parents=self.path_info.container_path_history(),
        )

    def _is_archive_path_skip(self, path_info) -> bool:
        return bool(self._skipper) and (
            self._skipper.is_walk_file_skip(path_info)
            or (
                not self.config.timestamps_ignore_archive_entry_mtimes
                and self._skipper.is_older_than_timestamp(path_info)
            )
        )

    def _walk_one_entry(self, archive, archiveinfo):
        path_info = self._create_path_info(archiveinfo)
        if self._is_archive_path_skip(path_info):
            self._skip_path_infos.add(path_info)
            return None
        if data := self._archive_readfile(archive, archiveinfo):
            path_info.set_data(data)
        return path_info

    def _consume_archive_timestamps(self, archive):
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
            yaml_str = yaml_str.decode(errors="replace")
            archive_sub_path = self.path_info.archive_pseudo_path() / path.parent
            self._timestamps.loads(archive_sub_path, yaml_str)
            if self._skipper:
                self._printer.consumed_timestamp(path)
            self._do_repack = True
        return tuple(non_treestamp_entries)

    def _copy_unchanged_files(self, archive) -> None:
        while self._skip_path_infos:
            path_info = self._skip_path_infos.pop()
            archiveinfo = path_info.archiveinfo
            if archiveinfo and (
                data := self._archive_readfile(archive, archiveinfo.info)
            ):
                path_info.set_data(data)
            self._optimized_contents.add(path_info)

    @override
    def walk(self) -> Generator[PathInfo]:
        """Walk an archive's entries."""
        self._printer.scan_archive(self.path_info)
        with self._get_archive() as archive:
            non_treestamp_entries = self._consume_archive_timestamps(archive)
            for archiveinfo in non_treestamp_entries:
                if path_info := self._walk_one_entry(archive, archiveinfo):
                    yield path_info
            # Always copy unchanged files: the scheduler decides
            # whether to repack after children are processed, but
            # we must read data while the archive is still open.
            self._copy_unchanged_files(archive)
        self._walk_finish()

    @override
    def hydrate_optimized_path_info(
        self, path_info: PathInfo, report: ReportStats
    ) -> None:
        super().hydrate_optimized_path_info(path_info, report)
        original_path = path_info.name()
        final_path = report.path
        if final_path and original_path != final_path:
            path_info.rename(final_path)
