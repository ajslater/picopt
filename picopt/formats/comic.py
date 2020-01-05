"""Optimize comic archives."""
import os
import shutil
import zipfile
from pathlib import Path
from typing import Callable, Optional, Set, Tuple

import rarfile  # type: ignore

from .. import PROGRAM_NAME, files, stats
from ..settings import Settings
from ..stats import ReportStats
from .format import Format

_CBZ_FORMAT: str = 'CBZ'
_CBR_FORMAT: str = 'CBR'

_CBR_EXT: str = '.cbr'
_CBZ_EXT: str = '.cbz'
_COMIC_EXTS: Set[str] = set((_CBR_EXT, _CBZ_EXT))

_ARCHIVE_TMP_DIR_PREFIX: str = PROGRAM_NAME+'_tmp_'
_NEW_ARCHIVE_SUFFIX: str = f'.{PROGRAM_NAME}-optimized'


class Comic(Format):
    """Comic format class."""

    BEST_ONLY: bool = False
    OUT_EXT: str = _CBZ_EXT
    FORMATS: Set[str] = set((_CBZ_FORMAT, _CBR_FORMAT))

    @staticmethod
    def comics():
        """
        Do nothing comic optimizer.

        Not used because comics are special and use walk.walk_comic_archive
        But currently neccissary to keep detect_format._is_program_selected()
        working
        """
        pass

    PROGRAMS: Tuple[Callable] = (comics,)

    @staticmethod
    def get_comic_format(path: Path) -> Optional[str]:
        """Return the comic format if it is a comic archive."""
        image_format = None
        filename_ext = path.suffix.lower()
        if filename_ext in _COMIC_EXTS:
            if zipfile.is_zipfile(path):
                image_format = _CBZ_FORMAT
            elif rarfile.is_rarfile(path):
                image_format = _CBR_FORMAT
        return image_format

    @staticmethod
    def _get_archive_tmp_dir(path: Path) -> Path:
        """Get the name of the working dir to use for this filename."""
        return path.parent.joinpath(_ARCHIVE_TMP_DIR_PREFIX + path.name)

    @staticmethod
    def comic_archive_uncompress(path: Path, image_format: str) \
            -> Tuple[Optional[Path], Optional[ReportStats]]: # noqa
        """
        Uncompress comic archives.

        Return the name of the working directory we uncompressed into.
        """
        if not Settings.comics:
            report = f'Skipping archive file: {path}'
            return None, ReportStats(path, report=report)

        if Settings.verbose:
            print(f"Extracting {path}...", end='')

        # create the tmpdir
        tmp_dir = Comic._get_archive_tmp_dir(path)
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir()

        # extract archvie into the tmpdir
        if image_format == _CBZ_FORMAT:
            with zipfile.ZipFile(path, 'r') as zfile:
                zfile.extractall(tmp_dir)
        elif image_format == _CBR_FORMAT:
            with rarfile.RarFile(path, 'r') as rfile:
                rfile.extractall(tmp_dir)
        else:
            report = f'{path} {image_format} is not a good format'
            return None, ReportStats(path, report=report)

        if Settings.verbose:
            print('done')

        return tmp_dir, None

    @staticmethod
    def _comic_archive_write_zipfile(new_path: Path, tmp_path: Path) -> None:
        """Zip up the files in the tempdir into the new filename."""
        if Settings.verbose:
            print('Rezipping archive', end='')
        with zipfile.ZipFile(new_path, 'w',
                             compression=zipfile.ZIP_DEFLATED) as new_zf:
            for root, _, filenames in os.walk(tmp_path):
                root_path = Path(root)
                for fname in filenames:
                    if Settings.verbose:
                        print('.', end='')
                    full_path = root_path.joinpath(fname)
                    archive_path = full_path.relative_to(tmp_path)
                    new_zf.write(full_path, archive_path, zipfile.ZIP_DEFLATED)

    @staticmethod
    def comic_archive_compress(args) -> ReportStats:
        """
        Call back by every optimization inside a comic archive.

        When they're all done it creates the new archive and cleans up.
        """
        try:
            path, old_format, settings, nag_about_gifs = args
            Settings.update(settings)
            tmp_path = Comic._get_archive_tmp_dir(path)

            # archive into new filename
            suffix = _NEW_ARCHIVE_SUFFIX + path.suffix
            new_path = path.with_suffix(suffix)

            Comic._comic_archive_write_zipfile(new_path, tmp_path)

            # Cleanup tmpdir
            if tmp_path.exists():
                if Settings.verbose:
                    print('.', end='')
                shutil.rmtree(tmp_path)
            if Settings.verbose:
                print('done.')

            report_stats = files.cleanup_after_optimize(path, new_path,
                                                        old_format,
                                                        _CBZ_FORMAT)
            report_stats.nag_about_gifs = nag_about_gifs
            stats.report_saved(report_stats)
            return report_stats
        except Exception as exc:
            print(exc)
            raise exc
