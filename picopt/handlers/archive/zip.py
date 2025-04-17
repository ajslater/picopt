"""Handler for zip files."""

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, is_zipfile

from termcolor import cprint

from picopt.formats import FileFormat
from picopt.handlers.archive.archive import ArchiveHandler
from picopt.handlers.container import ContainerHandler


class Zip(ArchiveHandler):
    """Ziplike container."""

    OUTPUT_FORMAT_STR: str = "ZIP"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)
    INPUT_FILE_FORMAT = OUTPUT_FILE_FORMAT
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    PROGRAMS = ((ContainerHandler.INTERNAL,),)
    ARCHIVE_CLASS = ZipFile

    @classmethod
    def _is_archive(cls, path: Path | BytesIO) -> bool:
        return is_zipfile(path)

    def _set_comment(self, archive: ZipFile) -> None:  # type: ignore[reportIncompatibleMethodOverride]
        """Set the comment from the archive."""
        if archive.comment:
            self.comment = archive.comment

    def _archive_for_write(self, output_buffer: BytesIO) -> ZipFile:
        return ZipFile(output_buffer, "w", compression=ZIP_DEFLATED, compresslevel=9)

    def _pack_info_one_file(self, archive, path_info):
        """Add one file to the new archive."""
        data = self._optimized_contents.pop(path_info)
        zipinfo = path_info.zipinfo
        if not zipinfo:
            return
        if (
            path_info.container_filename
            and path_info.container_filename != zipinfo.filename
        ):
            zipinfo.filename = path_info.container_filename
        if (
            not self.config.keep_metadata
            and zipinfo
            and zipinfo.compress_type == ZIP_STORED
        ):
            zipinfo.compress_type = ZIP_DEFLATED
        archive.writestr(zipinfo, data)
        if self.config.verbose:
            cprint(".", end="")


class Cbz(Zip):
    """CBZ Container."""

    OUTPUT_FORMAT_STR: str = "CBZ"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)
    INPUT_FILE_FORMAT = OUTPUT_FILE_FORMAT
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})


class EPub(Zip):
    """Epub Container."""

    # never convert inside epubs, breaks src links.
    CONVERT: bool = False
    OUTPUT_FORMAT_STR: str = "EPUB"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)
    INPUT_FILE_FORMAT = OUTPUT_FILE_FORMAT
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
