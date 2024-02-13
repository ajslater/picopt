"""Handler for zip files."""
from collections.abc import Generator
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo, is_zipfile

from rarfile import RarFile, RarInfo, is_rarfile
from termcolor import cprint

from picopt.formats import FileFormat
from picopt.handlers.container import ContainerHandler
from picopt.handlers.non_pil import NonPILIdentifier
from picopt.path import PathInfo


class Zip(NonPILIdentifier, ContainerHandler):
    """Ziplike container."""

    OUTPUT_FORMAT_STR: str = "ZIP"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS = ((ContainerHandler.INTERNAL,),)

    @classmethod
    def identify_format(cls, path_info: PathInfo) -> FileFormat | None:
        """Return the format if this handler can handle this path."""
        if is_zipfile(path_info.path_or_buffer()):
            return super().identify_format(path_info)
        return None

    def _get_archive(self) -> ZipFile:
        """Use the zipfile builtin for this archive."""
        if is_zipfile(self.original_path):
            archive = ZipFile(self.original_path, "r")
        else:
            msg = f"Unknown archive type: {self.original_path}"
            raise ValueError(msg)
        return archive

    def _set_comment(self, comment: bytes | None) -> None:
        """Set the comment from the archive."""
        if comment:
            self.comment = comment

    @staticmethod
    def to_zipinfo(archive_info: ZipInfo) -> ZipInfo:
        """Convert archive info to zipinfo."""
        return archive_info

    def unpack_into(self) -> Generator[PathInfo, None, None]:
        """Uncompress archive."""
        with self._get_archive() as archive:
            self._set_comment(archive.comment)
            for archive_info in archive.infolist():
                zipinfo = self.to_zipinfo(archive_info)
                path_info = PathInfo(
                    self.path_info.top_path,
                    self.path_info.mtime(),
                    self.path_info.convert,
                    self.path_info.is_case_sensitive,
                    zipinfo=zipinfo,
                    data=archive.read(zipinfo.filename),
                    container_paths=self.get_container_paths(),
                )
                yield path_info

    def pack_into(self) -> BytesIO:
        """Zip up the files in the tempdir into the new filename."""
        output_buffer = BytesIO()
        with ZipFile(
            output_buffer, "w", compression=ZIP_DEFLATED, compresslevel=9
        ) as new_zf:
            for path_info in tuple(self._optimized_contents):
                data = self._optimized_contents.pop(path_info)
                if not path_info.zipinfo:
                    continue
                zipinfo: ZipInfo = path_info.zipinfo
                if (
                    not self.config.keep_metadata
                    and zipinfo
                    and zipinfo.compress_type == ZIP_STORED
                ):
                    zipinfo.compress_type = ZIP_DEFLATED
                new_zf.writestr(zipinfo, data)
                if self.config.verbose:
                    cprint(".", end="")
            if self.comment:
                new_zf.comment = self.comment
                if self.config.verbose:
                    cprint(".", end="")
        return output_buffer


class Rar(Zip):
    """RAR Container."""

    INPUT_FORMAT_STR: str = "RAR"
    INPUT_SUFFIX: str = "." + INPUT_FORMAT_STR.lower()
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    PROGRAMS = (("unrar",),)

    @staticmethod
    def to_zipinfo(archive_info: RarInfo | ZipInfo) -> ZipInfo:
        """Convert RarInfo to ZipInfo."""
        zipinfo_kwargs = {}
        if archive_info.filename:
            zipinfo_kwargs["filename"] = archive_info.filename
        if archive_info.date_time:
            zipinfo_kwargs["date_time"] = archive_info.date_time
        return ZipInfo(**zipinfo_kwargs)

    @classmethod
    def identify_format(cls, path_info: PathInfo) -> FileFormat | None:
        """Return the format if this handler can handle this path."""
        file_format = None
        suffix = path_info.suffix().lower()
        if is_rarfile(path_info.path_or_buffer()) and suffix == cls.INPUT_SUFFIX:
            file_format = cls.INPUT_FILE_FORMAT
        return file_format

    def _get_archive(self) -> RarFile:  # type: ignore
        """Use the zipfile builtin for this archive."""
        if is_rarfile(self.original_path):
            archive = RarFile(self.original_path, mode="r")
        else:
            msg = f"Unknown archive type: {self.original_path}"
            raise ValueError(msg)
        return archive

    def _set_comment(self, comment: str | None) -> None:  # type: ignore
        """Set the comment from the archive."""
        if comment:
            self.comment = comment.encode()


class Cbz(Zip):
    """CBZ Container."""

    OUTPUT_FORMAT_STR: str = "CBZ"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})


class Cbr(Rar):
    """CBR Container."""

    INPUT_FORMAT_STR: str = "CBR"
    INPUT_SUFFIX: str = "." + INPUT_FORMAT_STR.lower()
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    OUTPUT_FORMAT_STR: str = "CBZ"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)


class EPub(Zip):
    """Epub Container."""

    # never convert inside epubs, breaks src links.
    CONVERT: bool = False
    OUTPUT_FORMAT_STR: str = "EPUB"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
