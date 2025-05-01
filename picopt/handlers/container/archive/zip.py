"""Handler for zip files."""

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, is_zipfile

from picopt.formats import FileFormat
from picopt.handlers.container.archive import PackingArchiveHandler
from picopt.handlers.handler import INTERNAL


class Zip(PackingArchiveHandler):
    """Ziplike container."""

    OUTPUT_FORMAT_STR: str = "ZIP"
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMAT = OUTPUT_FILE_FORMAT
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    PROGRAMS = ((INTERNAL,),)
    ARCHIVE_CLASS = ZipFile

    def __init__(self, *args, **kwargs):
        """Init delete_filenames."""
        super().__init__(*args, **kwargs)

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

    def _archive_for_write(self, output_buffer: BytesIO) -> ZipFile:
        return ZipFile(output_buffer, "x", compression=ZIP_DEFLATED, compresslevel=9)

    def _pack_info_one_file(self, archive, path_info):
        """Add one file to the new archive."""
        zipinfo = path_info.archiveinfo.to_zipinfo()
        if not self.config.keep_metadata and (
            not zipinfo.compress_type or zipinfo.compress_type == ZIP_STORED
        ):
            zipinfo.compress_type = ZIP_DEFLATED
        data = path_info.data()
        archive.writestr(zipinfo, data)


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
