"""Handler for zip files."""

from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from zipfile import ZIP_DEFLATED, ZIP_STORED, is_zipfile

from picopt.formats import FileFormat
from picopt.handlers.container.archive import PackingArchiveHandler
from picopt.handlers.handler import INTERNAL
from picopt.zipfile_remove import ZipFileWithRemove


class Zip(PackingArchiveHandler):
    """Ziplike container."""

    OUTPUT_FORMAT_STR: str = "ZIP"
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMAT = OUTPUT_FILE_FORMAT
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    PROGRAMS = ((INTERNAL,),)
    ARCHIVE_CLASS = ZipFileWithRemove

    def __init__(self, *args, convert: bool = False, **kwargs):
        """Init delete_filenames."""
        super().__init__(*args, **kwargs)
        self._patch_zipfile_on_disk = not convert and not self.path_info.archiveinfo
        self._delete_filenames = set()
        self._bytes_in = 0

    @classmethod
    def _is_archive(cls, path: Path | BytesIO) -> bool:
        return is_zipfile(path)

    @staticmethod
    def _archive_infolist(archive):
        return archive.infolist()

    def _archive_readfile(self, archive, archiveinfo):
        return archive.read(archiveinfo.filename)

    def _set_comment(self, archive) -> None:
        """Set the comment from the archive."""
        if archive.comment:
            self.comment = archive.comment

    def _mark_delete(self, filename: str | Path) -> None:
        """Mark delete for optimize_in_place_on_disk."""
        self._delete_filenames.add(str(filename))
        self._do_repack = True

    def _archive_for_write(self, output_buffer: BytesIO) -> ZipFileWithRemove:
        if self._patch_zipfile_on_disk:
            file = self.original_path
            mode = "a"
        else:
            file = output_buffer
            mode = "x"
        return ZipFileWithRemove(file, mode, compression=ZIP_DEFLATED, compresslevel=9)

    def _delete_files_before_write(self, archive):
        """Delete files in the archive on disk before appending new files.."""
        for path_info in self._optimized_contents:
            self._delete_filenames.add(path_info.original_name)
        while len(self._delete_filenames):
            filename = self._delete_filenames.pop()
            archive.remove(filename)

    def _pack_info_one_file(self, archive, path_info):
        """Add one file to the new archive."""
        zipinfo = path_info.archiveinfo.to_zipinfo()
        if zipinfo.filename in self._delete_filenames:
            return
        if not self.config.keep_metadata and (
            not zipinfo.compress_type or zipinfo.compress_type == ZIP_STORED
        ):
            zipinfo.compress_type = ZIP_DEFLATED
        data = path_info.data()
        archive.writestr(zipinfo, data)

    def _archive_write(self, archive):
        if self._patch_zipfile_on_disk:
            self._delete_files_before_write(archive)
        super()._archive_write(archive)

    def pack_into(self) -> BytesIO:
        """Do in place deletes on disk before writing if we can."""
        if self._patch_zipfile_on_disk:
            self._bytes_in = self.path_info.bytes_in()
        return super().pack_into()

    def _cleanup_filesystem_write_final_path(self, final_data_buffer: BinaryIO) -> None:
        if not self._patch_zipfile_on_disk:
            super()._cleanup_filesystem_write_final_path(final_data_buffer)

    def _cleanup_after_optimize_calculate_bytes(
        self, final_data_buffer: BinaryIO
    ) -> tuple[int, int]:
        if self._patch_zipfile_on_disk:
            bytes_in = self._bytes_in
            bytes_out = self.final_path.stat().st_size
        else:
            bytes_in, bytes_out = super()._cleanup_after_optimize_calculate_bytes(
                final_data_buffer
            )
        return bytes_in, bytes_out


class Cbz(Zip):
    """CBZ Container."""

    OUTPUT_FORMAT_STR: str = "CBZ"
    INPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FILE_FORMAT = INPUT_FILE_FORMAT


class EPub(Zip):
    """Epub Container."""

    OUTPUT_FORMAT_STR: str = "EPUB"
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMAT = OUTPUT_FILE_FORMAT
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    # never convert inside epubs, breaks src links.
    CONVERT_CHILDREN = False
