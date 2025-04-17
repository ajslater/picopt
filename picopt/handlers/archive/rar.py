"""RAR Handler."""

from io import BytesIO
from pathlib import Path
from types import MappingProxyType

from rarfile import RarFile, is_rarfile

from picopt.formats import FileFormat
from picopt.handlers.archive.zip import Zip


class Rar(Zip):
    """RAR Container."""

    INPUT_FORMAT_STR: str = "RAR"
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    # RAR is nonfree and often unable to repack with available tools. Always convert to Zip.
    OUTPUT_FORMAT_STR: str = "ZIP"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)
    PROGRAMS = (("unrar",),)
    ARCHIVE_CLASS = RarFile
    ZIPINFO_MAP = MappingProxyType({"filename": "filename", "date_time": "date_time"})

    @classmethod
    def _is_archive(cls, path: Path | BytesIO) -> bool:
        return is_rarfile(path)

    def _set_comment(self, archive: RarFile) -> None:  # type: ignore[reportIncompatibleMethodOverride]
        """Set the comment from the archive."""
        if archive.comment:
            self.comment = archive.comment.encode()


class Cbr(Rar):
    """CBR Container."""

    INPUT_FORMAT_STR: str = "CBR"
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    # RAR is nonfree and often unable to repack with available tools. Always convert to CBZ.
    OUTPUT_FORMAT_STR: str = "CBZ"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)
