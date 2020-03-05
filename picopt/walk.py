"""Walk the directory trees and files and call the optimizers."""
import multiprocessing
import os
import time

from multiprocessing.pool import AsyncResult
from multiprocessing.pool import Pool
from pathlib import Path
from typing import Any
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

from . import detect_format
from . import optimize
from . import stats
from . import timestamp
from .formats.comic import Comic
from .settings import Settings
from .stats import ReportStats
from .timestamp import Timestamp


class Walk(object):
    """Walk object for storing state of a walk run."""

    def __init__(self, settings: Settings) -> None:
        """Set the settings and initialize the threadpool & Timstamp."""
        self._settings = settings
        self._pool = Pool(self._settings.jobs)
        self._tso = Timestamp(self._settings)

    @staticmethod
    def _comic_archive_skip(args: Tuple[ReportStats]) -> ReportStats:
        return args[0]

    def walk_comic_archive(
        self, path: Path, image_format: str, optimize_after: Optional[float]
    ) -> Set[AsyncResult]:
        """
        Optimize a comic archive.

        This is done mostly inline to use the master processes process pool
        for workers. And to avoid calling back up into walk from a dedicated
        module or format processor. It does mean that we block on uncompress
        and on waiting for the contents subprocesses to compress.
        """
        # uncompress archive
        tmp_dir, report_stats = Comic.comic_archive_uncompress(
            self._settings, path, image_format
        )
        if tmp_dir is None:
            skip_args = tuple([report_stats])
            return set(
                [self._pool.apply_async(self._comic_archive_skip, args=(skip_args,))]
            )

        # optimize contents of archive
        archive_mtime = path.stat().st_mtime
        result_set = self.walk_dir(tmp_dir, optimize_after, True, archive_mtime)

        # wait for archive contents to optimize before recompressing
        nag_about_gifs = False
        for result in result_set:
            res = result.get()
            nag_about_gifs = nag_about_gifs or res.nag_about_gifs

        # recompress archive
        args = (path, image_format, self._settings, nag_about_gifs)
        return set([self._pool.apply_async(Comic.comic_archive_compress, args=(args,))])

    def _is_skippable(self, path: Path) -> bool:
        """Handle things that are not optimizable files."""
        # File types
        if not self._settings.follow_symlinks and path.is_symlink():
            if self._settings.verbose > 1:
                print(path, "is a symlink, skipping.")
            return True
        if path.name == timestamp.RECORD_FILENAME:
            return True
        if not path.exists():
            if self._settings.verbose:
                print(path, "was not found.")
            return True

        return False

    @staticmethod
    def _is_older_than_timestamp(
        path: Path, walk_after: Optional[float], archive_mtime: Optional[float]
    ) -> bool:
        if walk_after is None:
            return False

        # if the file is in an archive, use the archive time if it
        # is newer. This helps if you have a new archive that you
        # collected from someone who put really old files in it that
        # should still be optimised
        mtime = Timestamp.max_none((path.stat().st_mtime, archive_mtime))
        return mtime is not None and mtime <= walk_after

    def walk_file(
        self,
        filename: Path,
        walk_after: Optional[float],
        recurse: Optional[int] = None,
        archive_mtime: Optional[float] = None,
    ) -> Set[AsyncResult]:
        """Optimize an individual file."""
        path = Path(filename)
        result_set: Set[AsyncResult] = set()
        if self._is_skippable(path):
            return result_set

        walk_after = self._tso.get_walk_after(path, walk_after)

        # File is a directory
        if path.is_dir():
            return self.walk_dir(path, walk_after, recurse, archive_mtime)

        if self._is_older_than_timestamp(path, walk_after, archive_mtime):
            return result_set

        # Check image format
        #    try:
        image_format = detect_format.detect_file(self._settings, path)
        #    except Exception:
        #        res = settings.pool.apply_async(
        #            stats.ReportStats, (path,), {"error": "Detect Format"}
        #        )
        #        result_set.add(res)
        #        image_format = None

        if not image_format:
            return result_set

        if self._settings.list_only:
            # list only
            print(f"{path}: {image_format}")
            return result_set

        if detect_format.is_format_selected(
            self._settings, image_format, Comic.FORMATS, Comic.PROGRAMS
        ):
            # comic archive
            result_set |= self.walk_comic_archive(path, image_format, walk_after)
        else:
            # regular image
            args = [path, image_format, self._settings]
            result_set.add(
                self._pool.apply_async(optimize.optimize_image, args=(args,))
            )
        return result_set

    def walk_dir(
        self,
        dir_path: Path,
        walk_after: Optional[float],
        recurse: Optional[int] = None,
        archive_mtime: Optional[float] = None,
    ) -> Set[multiprocessing.pool.AsyncResult]:
        """Recursively optimize a directory."""
        if recurse is None:
            recurse = self._settings.recurse

        result_set: Set[AsyncResult] = set()
        if not recurse:
            return result_set

        for root, _, filenames in os.walk(dir_path):
            root_path = Path(root)
            filenames.sort()
            for filename in filenames:
                full_path = root_path / filename
                try:
                    results = self.walk_file(
                        full_path, walk_after, recurse, archive_mtime
                    )
                    result_set = result_set.union(results)
                except Exception:
                    print(f"Error with file: {full_path}")
                    raise

        return result_set

    def _walk_all_files(self) -> Tuple[Set[Path], int, int, bool, List[Any]]:
        """
        Optimize the files from the arugments list in two batches.

        One for absolute paths which are probably outside the current
        working directory tree and one for relative files.
        """
        # Init records
        record_dirs: Set[Path] = set()
        result_set: Set[AsyncResult] = set()

        for filename in self._settings.paths:
            path = Path(filename)
            # Record dirs to put timestamps in later
            if self._settings.recurse and path.is_dir():
                record_dirs.add(path)

            walk_after = self._tso.get_walk_after(path)
            # TODO is passing this recurse argument neccissary?
            results = self.walk_file(path, walk_after, self._settings.recurse)
            result_set = result_set.union(results)

        bytes_in = 0
        bytes_out = 0
        nag_about_gifs = False
        errors: List[Tuple[Path, str]] = []
        for result in result_set:
            res = result.get()
            if res.error:
                errors += [(res.final_path, res.error)]
                continue
            bytes_in += res.bytes_in
            bytes_out += res.bytes_out
            nag_about_gifs = nag_about_gifs or res.nag_about_gifs

        return record_dirs, bytes_in, bytes_out, nag_about_gifs, errors

    def run(self) -> bool:
        """Use preconfigured settings to optimize files."""
        if not self._settings.can_do:
            print("All optimizers are not available or disabled.")
            return False

        if self._settings.optimize_after is not None and self._settings.verbose:
            print("Optimizing after", time.ctime(self._settings.optimize_after))

        # Setup Multiprocessing
        # Optimize Files
        (
            record_dirs,
            bytes_in,
            bytes_out,
            nag_about_gifs,
            errors,
        ) = self._walk_all_files()

        # Shut down multiprocessing
        self._pool.close()
        self._pool.join()

        # Write timestamps
        for filename in record_dirs:
            self._tso.record_timestamp(filename)

        # Finish by reporting totals
        stats.report_totals(self._settings, bytes_in, bytes_out, nag_about_gifs, errors)
        return True
