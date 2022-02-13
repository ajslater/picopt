"""Optimize comic archives."""
import os
import shutil
import zipfile

from pathlib import Path
from typing import Callable, Optional, Tuple

import rarfile

from picopt import PROGRAM_NAME, files, stats
from picopt.extern import ExtArgs
from picopt.formats.comic_formats import CBR_FORMAT, CBZ_FORMAT
from picopt.formats.format import Format
from picopt.settings import Settings
from picopt.stats import ReportStats


_CBR_EXT: str = ".cbr"
_CBZ_EXT: str = ".cbz"

_ARCHIVE_TMP_DIR_PREFIX: str = PROGRAM_NAME + "_tmp_"
_NEW_ARCHIVE_SUFFIX: str = f".{PROGRAM_NAME}-optimized-cbz"


class Comic(Format):
    """Comic format class."""

    BEST_ONLY: bool = False
    OUT_EXT: str = _CBZ_EXT

    @staticmethod
    def comics(_: ExtArgs) -> str:
        """
        Do nothing comic optimizer.

        Not used because comics are special and use walk.walk_comic_archive
        But currently neccissary to keep detect_format._is_program_selected()
        working
        """
        return CBZ_FORMAT

    PROGRAMS: Tuple[Callable[[ExtArgs], str], ...] = (comics,)

    @staticmethod
    def get_comic_format(path: Path) -> Optional[str]:
        """Return the comic format if it is a comic archive."""
        image_format = None
        filename_ext = path.suffix.lower()
        if filename_ext == _CBZ_EXT and zipfile.is_zipfile(path):
            image_format = CBZ_FORMAT
        if filename_ext == _CBR_EXT and rarfile.is_rarfile(path):
            image_format = CBR_FORMAT
        return image_format

    @staticmethod
    def _get_archive_tmp_dir(path: Path) -> Path:
        """Get the name of the working dir to use for this filename."""
        filename = _ARCHIVE_TMP_DIR_PREFIX + path.name
        return path.parent / filename

    @staticmethod
    def _get_archive(path, image_format):
        if image_format == CBZ_FORMAT:  # and zipfile.is_zipfile(path):
            return zipfile.ZipFile(path, "r")
        elif image_format == CBR_FORMAT:  # and rarfile.is_rarfile(path):
            return rarfile.RarFile(path, "r")
        raise ValueError(f"Archive format {image_format} not supported")

    @staticmethod
    def comic_archive_uncompress(
        settings: Settings, path: Path, image_format: str
    ) -> Tuple[Optional[Path], Optional[ReportStats], Optional[bytes]]:
        """
        Uncompress comic archives.

        Return the name of the working directory we uncompressed into.
        """
        if not settings.comics:
            report = f"Skipping archive file: {path}"
            return None, ReportStats(path, report=report), None

        if settings.verbose:
            print(f"Extracting {path}...", end="")

        # create the tmpdir
        tmp_dir = Comic._get_archive_tmp_dir(path)
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir()

        # extract archive into the tmpdir
        try:
            with Comic._get_archive(path, image_format) as archive:
                archive.extractall(tmp_dir)
                comment = archive.comment
                if isinstance(comment, str):
                    # rarfile exports unicode comments, zipfile bytes :/
                    # zipfile expects bytes for assignment later.
                    comment = comment.encode()
        except Exception:
            report = f"{path} {image_format} is not a good format"
            return None, ReportStats(path, report=report), None

        if settings.verbose:
            print("done")

        return tmp_dir, None, comment

    @staticmethod
    def _comic_archive_write_zipfile(
        settings: Settings, new_path: Path, tmp_path: Path, comment: bytes
    ) -> None:
        """Zip up the files in the tempdir into the new filename."""
        if settings.verbose:
            print("Rezipping archive", end="")
        with zipfile.ZipFile(
            new_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as new_zf:
            for root, _, filenames in os.walk(tmp_path):
                root_path = Path(root)
                filenames.sort()
                for fname in sorted(filenames):
                    if settings.verbose:
                        print(".", end="")
                    full_path = root_path / fname
                    archive_path = full_path.relative_to(tmp_path)
                    new_zf.write(full_path, archive_path, zipfile.ZIP_DEFLATED)
            if comment:
                new_zf.comment = comment

    @staticmethod
    def comic_archive_compress(args: Tuple[Path, str, Settings, bytes]) -> ReportStats:
        """
        Call back by every optimization inside a comic archive.

        When they're all done it creates the new archive and cleans up.
        """
        try:
            old_path, old_format, settings, comment = args
            tmp_path = Comic._get_archive_tmp_dir(old_path)

            # archive into new filename
            new_path = old_path.with_suffix(_NEW_ARCHIVE_SUFFIX)
            Comic._comic_archive_write_zipfile(settings, new_path, tmp_path, comment)

            # Cleanup tmpdir
            if settings.verbose:
                print(".", end="")
            shutil.rmtree(tmp_path)
            if settings.verbose:
                print("done.")

            report_stats = files.cleanup_after_optimize(
                settings, old_path, new_path, old_format, CBZ_FORMAT
            )
            stats.report_saved(settings, report_stats)
            return report_stats
        except Exception as exc:
            print(exc)
            raise exc
