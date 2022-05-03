"""Handler for zip files."""
import os

from pathlib import Path
from typing import Optional, Union
from zipfile import ZIP_DEFLATED, ZipFile, is_zipfile

from PIL import Image, UnidentifiedImageError
from rarfile import RarFile, is_rarfile

from picopt.handlers.container import ContainerHandler
from picopt.handlers.handler import Format


class Zip(ContainerHandler):
    """Ziplike container."""

    OUTPUT_FORMAT: str = "ZIP"
    OUTPUT_FORMAT_OBJ: Format = Format(OUTPUT_FORMAT)
    INPUT_FORMAT_RAR: str = "RAR"
    INPUT_FORMAT_OBJ_RAR: Format = Format(INPUT_FORMAT_RAR)
    RAR_SUFFIX: str = "." + INPUT_FORMAT_RAR.lower()
    PROGRAMS: dict[str, Optional[str]] = {ContainerHandler.INTERNAL: None}

    @classmethod
    def identify_format(cls, path: Path) -> Optional[Format]:
        """Return the format if this handler can handle this path."""
        format = None
        suffix = path.suffix.lower()
        if is_zipfile(path) and suffix == cls.output_suffix():
            format = cls.OUTPUT_FORMAT_OBJ
        elif is_rarfile(path) and suffix == cls.RAR_SUFFIX:
            format = cls.INPUT_FORMAT_OBJ_RAR
        return format

    def _get_archive(self) -> Union[ZipFile, RarFile]:
        """Use the zipfile builtin for this archive."""
        if is_zipfile(self.original_path):
            archive = ZipFile(self.original_path, "r")
        elif is_rarfile(self.original_path):
            archive = RarFile(self.original_path, "r")
        else:
            raise ValueError(f"Unknown archive type: {self.original_path}")
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
                        print(".", end="")
                    full_path = root_path / fname
                    if self._is_image(full_path):
                        # Do not deflate images in zipfile.
                        # Picopte should have already achieved maximum
                        # compression over deflate.
                        compress_type = None
                    else:
                        compress_type = ZIP_DEFLATED
                    archive_path = full_path.relative_to(self.tmp_container_dir)
                    new_zf.write(full_path, archive_path, compress_type)
            if self.comment:
                new_zf.comment = self.comment


class CBZ(Zip):
    """CBZ Container."""

    OUTPUT_FORMAT: str = "CBZ"
    OUTPUT_FORMAT_OBJ: Format = Format(OUTPUT_FORMAT)
    INPUT_FORMAT_RAR: str = "CBR"
    INPUT_FORMAT_OBJ_RAR: Format = Format(INPUT_FORMAT_RAR)
    RAR_SUFFIX: str = "." + INPUT_FORMAT_RAR.lower()


class EPub(Zip):
    """Epub Container."""

    OUTPUT_FORMAT: str = "EPUB"
    OUTPUT_FORMAT_OBJ: Format = Format(OUTPUT_FORMAT)
    CONVERT: bool = False
