"""Walk the directory trees and files and call the optimizers."""
import os
import time

from multiprocessing.pool import AsyncResult, Pool
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from confuse.templates import AttrDict

from picopt import PROGRAM_NAME
from picopt.handlers.container import ContainerHandler
from picopt.handlers.get_handler import get_handler
from picopt.handlers.handler import Handler
from picopt.handlers.image import ImageHandler
from picopt.stats import ReportStats
from picopt.timestamp import Timestamp


class Walk:
    """Walk object for storing state of a walk run."""

    def __init__(self, config: AttrDict) -> None:
        """Initialize."""
        self._pool = Pool()
        self._timestamps: Dict[Path, Timestamp] = {}
        self._config: AttrDict = config

    def walk_container(
        self,
        path: Path,
        handler: ContainerHandler,
        after: Optional[float],
    ) -> Set[AsyncResult]:
        """
        Optimize a comic archive.

        Blocks on uncompress.
        """
        # uncompress archive
        try:
            # XXX blocks on unpack
            # optimize contents of archive
            archive_mtime = path.stat().st_mtime

            handler.unpack()
            # Use a None top_path to not report archive internal timestamps back up
            #   to the timestamp file.
            result_set = self.walk_dir(
                handler.tmp_container_dir, after, None, archive_mtime
            )

            # wait for archive contents to optimize before recompressing
            # XXX blocks on waiting for container to complete.
            for result in result_set:
                result.get()

            # recompress archive
            final_result = self._pool.apply_async(handler.repack)
        except Exception as exc:
            args = tuple([exc])
            final_result = self._pool.apply_async(handler.error, args=args)
        return set([final_result])

    def _is_skippable(self, path: Path, top_path: Optional[Path]) -> bool:
        """Handle things that are not optimizable files."""
        # File types
        skip = False
        if not self._config.follow_symlinks and path.is_symlink():
            if self._config.verbose > 1:
                print(path, "is a symlink, skipping.")
            skip = True
        elif top_path and path.name == self._timestamps[top_path].old_timestamp_name:
            if top_path is not None:
                self._timestamps[top_path].upgrade_old_timestamp(path)
            skip = True
        elif top_path and path.name == self._timestamps[top_path].timestamps_name:
            if top_path is not None and path.parent != top_path:
                self._timestamps[top_path].consume_child_timestamps(path)
            skip = True
        elif path.name.rfind(Handler.WORKING_SUFFIX) > -1:
            path.unlink()
            skip = True
        elif not path.exists():
            if self._config.verbose:
                print(path, "was not found.")
            skip = True

        if skip and self._config.verbose > 1:
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
        top_path: Optional[Path],
        archive_mtime: Optional[float] = None,
    ) -> Set[AsyncResult]:
        """Optimize an individual file."""
        path = Path(filename)
        result_set: Set[AsyncResult] = set()
        if self._is_skippable(path, top_path):
            return result_set

        if top_path is not None:
            timestamps = self._timestamps[top_path]
            if self._config.after is not None:
                walk_after = self._config.after
            else:
                walk_after = timestamps.get_timestamp_recursive_up(path)

        # File is a directory
        if path.is_dir():
            return self.walk_dir(path, walk_after, top_path, archive_mtime)

        if self._is_older_than_timestamp(path, walk_after, archive_mtime):
            return result_set

        handler = get_handler(self._config, path)

        if handler is None:
            return result_set

        if self._config.list_only:
            print(f"{path}: {handler.__class__.__name__}")
            return result_set

        if isinstance(handler, ContainerHandler):
            result_set |= self.walk_container(path, handler, walk_after)
        elif isinstance(handler, ImageHandler):
            result_set.add(self._pool.apply_async(handler.optimize_image))
        else:
            raise ValueError(f"bad handler {handler}")
        return result_set

    def walk_dir(
        self,
        dir_path: Path,
        walk_after: Optional[float],
        top_path: Optional[Path],
        archive_mtime: Optional[float] = None,
    ) -> Set[AsyncResult]:
        """Recursively optimize a directory."""
        result_set: Set[AsyncResult] = set()
        if not self._config.recurse:
            return result_set

        for root, _, filenames in os.walk(dir_path):
            root_path = Path(root)
            filenames.sort()
            for filename in filenames:
                full_path = root_path / filename
                try:
                    results = self.walk_file(
                        full_path, walk_after, top_path, archive_mtime
                    )
                    result_set = result_set.union(results)
                except Exception:
                    print(f"Error with file: {full_path}")
                    raise

        return result_set

    def _should_record_timestamp(self, path: Path) -> bool:
        """Determine if we should we record a timestamp at all."""
        return (
            (
                not self._config.test
                and not self._config.list_only
                and self._config.record_timestamp
            )
            and (self._config.follow_symlinks or not path.is_symlink())
            and path.exists()
        )

    def _walk_all_files(self, top_paths: Set[Path]) -> Tuple[int, int, List[Any]]:
        """
        Optimize the files from the arguments list in two batches.

        One for absolute paths which are probably outside the current
        working directory tree and one for relative files.
        """
        # Init records
        result_sets: Dict[Path, Set[AsyncResult]] = {}

        for top_path in sorted(top_paths):
            timestamps = Timestamp(PROGRAM_NAME, top_path, self._config.verbose)
            # TODO should walk_after still work like this?
            self._timestamps[top_path] = timestamps
            # XXX This should probably be moved to ts init.
            timestamps.upgrade_old_parent_timestamps(top_path)
            timestamps.dump_timestamps()
            # TODO is this a dupe as it gets done in walk_file fast too
            # walk_after = timestamps.get_walk_after(top_path)
            walk_after = None
            result_set = self.walk_file(top_path, walk_after, top_path)
            result_sets[top_path] = result_set

        bytes_in = 0
        bytes_out = 0
        errors: List[Tuple[Path, List[str]]] = []
        for top_path, result_set in result_sets.items():
            for result in result_set:
                res = result.get()
                if res.errors:
                    errors += [(res.final_path, res.errors)]
                    continue
                # APPEND EVERY FILE'S TIMESTAMP after its done.
                timestamps = self._timestamps[top_path]
                if self._should_record_timestamp(res.final_path):
                    timestamps.record_timestamp(res.final_path)
                bytes_in += res.bytes_in
                bytes_out += res.bytes_out

            timestamps = self._timestamps[top_path]

            if self._should_record_timestamp(top_path):
                timestamps.record_timestamp(top_path)
                timestamps.compact_timestamps(top_path)

        return bytes_in, bytes_out, errors

    def run(self) -> bool:
        """Optimize all configured files."""
        top_paths = set()
        for top_path_fn in self._config.paths:
            top_path = Path(top_path_fn)
            if not top_path.exists():
                print(f"Path does not exist: {top_path_fn}")
                return False
            top_paths.add(top_path)

        if self._config.after is not None and self._config.verbose:
            print("Optimizing after", time.ctime(self._config.after))

        if self._config.jobs:
            self._pool = Pool(self._config.jobs)

        # Optimize Files
        (
            bytes_in,
            bytes_out,
            errors,
        ) = self._walk_all_files(top_paths)

        # Shut down multiprocessing
        self._pool.close()
        self._pool.join()

        # Finish by reporting totals
        report_stats = ReportStats(
            self._config, Path(), bytes_count=(bytes_in, bytes_out), errors=errors
        )
        report_stats.report_totals()
        return True
