"""Walk the directory trees and files and call the optimizers."""
import multiprocessing
import os
import time

from copy import deepcopy
from multiprocessing.pool import AsyncResult, Pool
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from picopt import detect_format, stats
from picopt.formats.comic import Comic
from picopt.formats.comic_formats import COMIC_FORMATS
from picopt.optimize import TMP_SUFFIX, optimize_image
from picopt.settings import Settings
from picopt.stats import ReportStats
from picopt.timestamp import Timestamp


class Walk:
    """Walk object for storing state of a walk run."""

    def __init__(self) -> None:
        """Initialize."""
        self._pool = Pool()
        self._timestamps: Dict[Path, Timestamp] = {}

    @staticmethod
    def _comic_archive_skip(args: Tuple[ReportStats]) -> ReportStats:
        return args[0]

    def walk_comic_archive(
        self,
        path: Path,
        image_format: str,
        optimize_after: Optional[float],
        settings: Settings,
    ) -> Set[AsyncResult]:
        """
        Optimize a comic archive.

        This is done mostly inline to use the master processes process pool
        for workers. And to avoid calling back up into walk from a dedicated
        module or format processor. It does mean that we block on uncompress
        and on waiting for the contents subprocesses to compress.
        """
        # Force settings true for going inside comics

        settings = deepcopy(settings)
        settings.recurse = True

        # uncompress archive
        tmp_dir, report_stats, comment = Comic.comic_archive_uncompress(
            settings, path, image_format
        )
        if tmp_dir is None:
            skip_args = (report_stats,)
            return set(
                [self._pool.apply_async(self._comic_archive_skip, args=(skip_args,))]
            )

        # optimize contents of archive
        archive_mtime = path.stat().st_mtime
        # Use a None top_path to not report archive internal timestamps back up
        #   to the timestamp file.
        result_set = self.walk_dir(
            tmp_dir, optimize_after, settings, None, archive_mtime
        )

        # wait for archive contents to optimize before recompressing
        for result in result_set:
            result.get()

        # recompress archive
        args = (path, image_format, settings, comment)
        return set([self._pool.apply_async(Comic.comic_archive_compress, args=(args,))])

    def _is_skippable(
        self, path: Path, settings: Settings, top_path: Optional[Path]
    ) -> bool:
        """Handle things that are not optimizable files."""
        # File types
        skip = False
        if not settings.follow_symlinks and path.is_symlink():
            if settings.verbose > 1:
                print(path, "is a symlink, skipping.")
            skip = True
        elif path.name == Timestamp.OLD_TIMESTAMP_NAME:
            if top_path is not None:
                self._timestamps[top_path].upgrade_old_timestamp(path)
            skip = True
        elif path.name == Timestamp.TIMESTAMPS_NAME:
            if top_path is not None and path.parent != top_path:
                self._timestamps[top_path].consume_child_timestamps(path)
            skip = True
        elif path.name.endswith(TMP_SUFFIX):
            path.unlink()
            skip = True
        elif not path.exists():
            if settings.verbose:
                print(path, "was not found.")
            skip = True

        if skip and settings.verbose > 1:
            print(f"skip {path}")

        return skip

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
        settings: Settings,
        top_path: Optional[Path],
        archive_mtime: Optional[float] = None,
    ) -> Set[AsyncResult]:
        """Optimize an individual file."""
        path = Path(filename)
        result_set: Set[AsyncResult] = set()
        if self._is_skippable(path, settings, top_path):
            return result_set

        if top_path is not None:
            timestamps = self._timestamps[top_path]
            if settings.optimize_after is not None:
                walk_after = settings.optimize_after
            else:
                walk_after = timestamps.get_timestamp_recursive_up(path)

        # File is a directory
        if path.is_dir():
            return self.walk_dir(path, walk_after, settings, top_path, archive_mtime)

        if self._is_older_than_timestamp(path, walk_after, archive_mtime):
            return result_set

        # Check image format
        #    try:
        image_format = detect_format.detect_file(settings, path)
        #    except Exception:
        #        res = settings.pool.apply_async(
        #            stats.ReportStats, (path,), {"error": "Detect Format"}
        #        )
        #        result_set.add(res)
        #        image_format = None

        if not image_format:
            return result_set

        if settings.list_only:
            # list only
            print(f"{path}: {image_format}")
            return result_set

        if detect_format.is_format_selected(
            settings, image_format, COMIC_FORMATS, Comic.PROGRAMS
        ):
            # comic archive
            result_set |= self.walk_comic_archive(
                path, image_format, walk_after, settings
            )
        else:
            # regular image
            args = (path, image_format, settings)
            result_set.add(self._pool.apply_async(optimize_image, args=(args,)))
        return result_set

    def walk_dir(
        self,
        dir_path: Path,
        walk_after: Optional[float],
        settings: Settings,
        top_path: Optional[Path],
        archive_mtime: Optional[float] = None,
    ) -> Set[AsyncResult]:
        """Recursively optimize a directory."""
        result_set: Set[AsyncResult] = set()
        if not settings.recurse:
            return result_set

        # NEW DIR, NEW SETTINGS
        settings = settings.clone(dir_path)

        for root, _, filenames in os.walk(dir_path):
            root_path = Path(root)
            filenames.sort()
            for filename in filenames:
                full_path = root_path / filename
                try:
                    results = self.walk_file(
                        full_path, walk_after, settings, top_path, archive_mtime
                    )
                    result_set = result_set.union(results)
                except Exception:
                    print(f"Error with file: {full_path}")
                    raise

        return result_set

    @staticmethod
    def _should_record_timestamp(settings: Settings, path: Path) -> bool:
        """Determine if we should we record a timestamp at all."""
        return (
            (not settings.test and not settings.list_only and settings.record_timestamp)
            and (settings.follow_symlinks or not path.is_symlink())
            and path.exists()
        )

    def _walk_all_files(
        self, settings: Settings, top_paths: Set[Path]
    ) -> Tuple[int, int, List[Any]]:
        """
        Optimize the files from the arguments list in two batches.

        One for absolute paths which are probably outside the current
        working directory tree and one for relative files.
        """
        # Init records
        result_sets: Dict[Path, Set[AsyncResult]] = {}

        for top_path in sorted(top_paths):
            timestamps = Timestamp(top_path, settings.verbose)
            # TODO should walk_after still work like this?
            self._timestamps[top_path] = timestamps
            # XXX This should probably be moved to ts init.
            timestamps.upgrade_old_parent_timestamps(top_path)
            timestamps.dump_timestamps()
            # TODO is this a dupe as it gets done in walk_file fast too
            # walk_after = timestamps.get_walk_after(top_path)
            walk_after = None
            result_set = self.walk_file(top_path, walk_after, settings, top_path)
            result_sets[top_path] = result_set

        bytes_in = 0
        bytes_out = 0
        errors: List[Tuple[Path, str]] = []
        for top_path, result_set in result_sets.items():
            for result in result_set:
                res = result.get()
                if res.error:
                    errors += [(res.final_path, res.error)]
                    continue
                # APPEND EVERY FILE'S TIMESTAMP after its done.
                timestamps = self._timestamps[top_path]
                if self._should_record_timestamp(settings, res.final_path):
                    timestamps.record_timestamp(res.final_path)
                bytes_in += res.bytes_in
                bytes_out += res.bytes_out

            timestamps = self._timestamps[top_path]

            if self._should_record_timestamp(settings, top_path):
                timestamps.record_timestamp(top_path)
                timestamps.compact_timestamps(top_path)

        return bytes_in, bytes_out, errors

    def run(self, settings: Settings) -> bool:
        """Use preconfigured settings to optimize files."""
        if not settings.can_do:
            print("No optimizers are available or all optimizers are disabled.")
            return False

        top_paths = set()
        for top_path_fn in settings.paths:
            top_path = Path(top_path_fn)
            if not top_path.exists():
                print(f"Path does not exist: {top_path_fn}")
                return False
            top_paths.add(top_path)

        if settings.optimize_after is not None and settings.verbose:
            print("Optimizing after", time.ctime(settings.optimize_after))

        # Setup Multiprocessing
        if settings.jobs != multiprocessing.cpu_count():
            # unusual situation, people usually don't specify jobs
            self._pool = Pool(settings.jobs)

        # Optimize Files
        (
            bytes_in,
            bytes_out,
            errors,
        ) = self._walk_all_files(settings, top_paths)

        # Shut down multiprocessing
        self._pool.close()
        self._pool.join()

        # Finish by reporting totals
        stats.report_totals(settings, bytes_in, bytes_out, errors)
        return True
