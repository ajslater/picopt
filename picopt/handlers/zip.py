"""Handler for zip files."""
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, is_zipfile

from PIL import Image, UnidentifiedImageError
from rarfile import RarFile, is_rarfile
from termcolor import cprint

from picopt.formats import FileFormat
from picopt.handlers.container import ContainerHandler


class Zip(ContainerHandler):
    """Ziplike container."""

    OUTPUT_FORMAT_STR: str = "ZIP"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS = ((ContainerHandler.INTERNAL,),)

    @classmethod
    def identify_format(cls, path: Path) -> FileFormat | None:
        """Return the format if this handler can handle this path."""
        file_format = None
        suffix = path.suffix.lower()
        if is_zipfile(path) and suffix == cls.get_default_suffix():
            file_format = cls.OUTPUT_FILE_FORMAT
        return file_format

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

    def unpack_into(self) -> None:
        """Uncompress archive."""
        with self._get_archive() as archive:
            archive.extractall(self.tmp_container_dir)
            self._set_comment(archive.comment)

    @staticmethod
    def _is_image(path: Path) -> bool:
        """Is a file an image."""
        result = False
        try:
            with Image.open(path, mode="r") as image:
                if image.format:
                    result = True
            image.close()
        except UnidentifiedImageError:
            pass
        return result

    def pack_into(self, working_path: Path) -> None:
        """Zip up the files in the tempdir into the new filename."""
        with ZipFile(
            working_path, "w", compression=ZIP_DEFLATED, compresslevel=9
        ) as new_zf:
            for root, _, filenames in os.walk(self.tmp_container_dir):
                root_path = Path(root)
                for fname in sorted(filenames):
                    if self.config.verbose:
                        cprint(".", end="")
                    full_path = root_path / fname
                    # Do not deflate images in zipfile.
                    # Picopte should have already achieved maximum
                    # compression over deflate.
                    compress_type = None if self._is_image(full_path) else ZIP_DEFLATED
                    archive_path = full_path.relative_to(self.tmp_container_dir)
                    new_zf.write(full_path, archive_path, compress_type)
            if self.comment:
                new_zf.comment = self.comment


class Rar(Zip):
    """RAR Container."""

    INPUT_FORMAT_STR: str = "RAR"
    INPUT_SUFFIX: str = "." + INPUT_FORMAT_STR.lower()
    INPUT_FILE_FORMAT = FileFormat(INPUT_FORMAT_STR)
    INPUT_FILE_FORMATS = frozenset({INPUT_FILE_FORMAT})
    PROGRAMS = (("unrar",),)

    @classmethod
    def identify_format(cls, path: Path) -> FileFormat | None:
        """Return the format if this handler can handle this path."""
        file_format = None
        suffix = path.suffix.lower()
        if is_rarfile(path) and suffix == cls.INPUT_SUFFIX:
            file_format = cls.INPUT_FILE_FORMAT
        return file_format

    def _get_archive(self) -> RarFile:  # type: ignore
        """Use the zipfile builtin for this archive."""
        if is_rarfile(self.original_path):
            archive = RarFile(self.original_path)
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
