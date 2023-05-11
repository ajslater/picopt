"""Handler for zip files."""
import os
from pathlib import Path
from typing import Optional, Union
from zipfile import ZIP_DEFLATED, ZipFile, is_zipfile

from PIL import Image, UnidentifiedImageError
from rarfile import RarFile, is_rarfile
from termcolor import cprint

from picopt.handlers.container import ContainerHandler
from picopt.handlers.handler import FileFormat


class Zip(ContainerHandler):
    """Ziplike container."""

    OUTPUT_FORMAT_STR: str = "ZIP"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)
    INPUT_FORMAT_STR_RAR: str = "RAR"
    INPUT_FILE_FORMAT_RAR: FileFormat = FileFormat(INPUT_FORMAT_STR_RAR)
    RAR_SUFFIX: str = "." + INPUT_FORMAT_STR_RAR.lower()
    PROGRAMS: dict[str, Optional[str]] = {ContainerHandler.INTERNAL: None}

    @classmethod
    def identify_format(cls, path: Path) -> Optional[FileFormat]:
        """Return the format if this handler can handle this path."""
        file_format = None
        suffix = path.suffix.lower()
        if is_zipfile(path) and suffix == cls.get_default_suffix():
            file_format = cls.OUTPUT_FILE_FORMAT
        elif is_rarfile(path) and suffix == cls.RAR_SUFFIX:
            file_format = cls.INPUT_FILE_FORMAT_RAR
        return file_format

    def _get_archive(self) -> Union[ZipFile, RarFile]:
        """Use the zipfile builtin for this archive."""
        if is_zipfile(self.original_path):
            archive = ZipFile(self.original_path, "r")
        elif is_rarfile(self.original_path):
            archive = RarFile(self.original_path, "r")
        else:
            msg = f"Unknown archive type: {self.original_path}"
            raise ValueError(msg)
        return archive

    def _set_comment(self, comment: Union[str, bytes, None]) -> None:
        """Set the comment from the archive."""
        if type(comment) is str:
            self.comment = comment.encode()
        elif type(comment) is bytes:
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


class CBZ(Zip):
    """CBZ Container."""

    OUTPUT_FORMAT_STR: str = "CBZ"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)
    INPUT_FORMAT_STR_RAR: str = "CBR"
    INPUT_FILE_FORMAT_RAR: FileFormat = FileFormat(INPUT_FORMAT_STR_RAR)
    RAR_SUFFIX: str = "." + INPUT_FORMAT_STR_RAR.lower()


class EPub(Zip):
    """Epub Container."""

    OUTPUT_FORMAT_STR: str = "EPUB"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR)
    CONVERT: bool = False
