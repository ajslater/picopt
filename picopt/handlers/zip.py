"""Handler for zip files."""
import os

from pathlib import Path
from typing import Optional, Union
from zipfile import ZIP_DEFLATED, ZipFile, is_zipfile

from rarfile import RarFile, is_rarfile

from picopt.handlers.container import ContainerHandler
from picopt.handlers.handler import Format


class Zip(ContainerHandler):
    """Ziplike container."""

    FORMAT_STR = "ZIP"
    FORMAT = Format(FORMAT_STR)
    NATIVE_FORMATS = set((FORMAT,))
    IMPLIES_RECURSE = True
    INTERNAL = True
    SUFFIX = "." + FORMAT_STR.lower()
    RAR_FORMAT_STR = "RAR"
    RAR_SUFFIX = "." + RAR_FORMAT_STR.lower()
    RAR_FORMAT = Format(RAR_FORMAT_STR)

    @classmethod
    def can_handle(cls, path: Path) -> Optional[Format]:
        """Is this a zipfile with a .zip extension."""
        format = None
        suffix = path.suffix.lower()
        if is_zipfile(path) and suffix == cls.SUFFIX:
            format = cls.FORMAT
        elif is_rarfile(path) and suffix == cls.RAR_SUFFIX:
            format = cls.RAR_FORMAT
        return format

    def get_archive(self) -> Union[ZipFile, RarFile]:
        """Use the zipfile builtin for this archive."""
        if is_zipfile(self.original_path):
            archive = ZipFile(self.original_path, "r")
        elif is_rarfile(self.original_path):
            archive = RarFile(self.original_path, "r")
        else:
            raise ValueError(f"Unknown archive type: {self.original_path}")
        return archive

    def set_comment(self, comment: Union[str, bytes, None]) -> None:
        """Set the comment from the archive."""
        if type(comment) is str:
            self.comment = comment.encode()
        elif type(comment) is bytes:
            self.comment = comment

    def unpack_into(self) -> None:
        """Uncompress archive."""
        with self.get_archive() as archive:
            archive.extractall(self.tmp_container_dir)
            self.set_comment(archive.comment)

    def create_container(self, working_path: Path) -> None:
        """Zip up the files in the tempdir into the new filename."""
        if self.config.verbose:
            print("Rezipping archive", end="")
        with ZipFile(
            working_path, "w", compression=ZIP_DEFLATED, compresslevel=9
        ) as new_zf:
            for root, _, filenames in os.walk(self.tmp_container_dir):
                root_path = Path(root)
                filenames.sort()
                for fname in sorted(filenames):
                    if self.config.verbose:
                        print(".", end="")
                    full_path = root_path / fname
                    archive_path = full_path.relative_to(self.tmp_container_dir)
                    new_zf.write(full_path, archive_path, ZIP_DEFLATED)
            if self.comment:
                new_zf.comment = self.comment


class CBZ(Zip):
    """CBZ Container."""

    FORMAT_STR = "CBZ"
    SUFFIX = "." + FORMAT_STR.lower()
    FORMAT = Format(FORMAT_STR)
    NATIVE_FORMATS = set((FORMAT,))
    RAR_FORMAT_STR = "CBR"
    RAR_SUFFIX = "." + RAR_FORMAT_STR.lower()
    RAR_FORMAT = Format(RAR_FORMAT_STR)
