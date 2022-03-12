"""Walk the directory trees and files and call the optimizers."""
import os
import time

from dataclasses import dataclass, field
from multiprocessing.pool import AsyncResult, Pool
from pathlib import Path
from queue import SimpleQueue
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from confuse.templates import AttrDict
from humanize import naturalsize

from picopt import PROGRAM_NAME
from picopt.config import TIMESTAMPS_CONFIG_KEYS
from picopt.handlers.container import ContainerHandler
from picopt.handlers.factory import create_handler
from picopt.handlers.handler import Handler
from picopt.handlers.image import ImageHandler
from picopt.old_timestamps import migrate_timestamps
from picopt.stats import ReportStats
from picopt.timestamps import Timestamps


@dataclass
class DirResult:
    """Results from a directory."""

    path: Path
    results: List


@dataclass
class ContainerDirResult(DirResult):
    """Results from a container."""

    handler: ContainerHandler


@dataclass
class ContainerRepackResult:
    """Task to fire off repack once all container optimizations are done."""

    handler: ContainerHandler


@dataclass
class Totals:
    """Totals for final report."""

    bytes_in: int = 0
    bytes_out: int = 0
    errors: List[ReportStats] = field(default_factory=list)


class Walk:
    """Walk object for storing state of a walk run."""

    def __init__(self, config: AttrDict) -> None:
        """Initialize."""
        self._config: AttrDict = config
        config_paths: Sequence[Path] = self._config.paths
        self._top_paths: Tuple[Path, ...] = tuple(sorted(set(config_paths)))
        self._timestamps: Dict[Path, Timestamps] = {}
        if self._config.jobs:
            self._pool = Pool(self._config.jobs)
        else:
            self._pool = Pool()

    def _get_timestamps(self, top_path: Path) -> Timestamps:
        dirpath = Timestamps.dirpath(top_path)
        return self._timestamps[dirpath]

    def _is_skippable(self, path: Path) -> bool:
        """Handle things that are not optimizable files."""
        # File types
        skip = False
        if not self._config.follow_symlinks and path.is_symlink():
            if self._config.verbose > 1:
                print(f"Skip symlink {path}")
            skip = True
        elif path.name == self.timestamps_filename:
            skip = True
        elif path.name.rfind(Handler.WORKING_SUFFIX) > -1:
            # auto-clean old working temp files if encountered.
            path.unlink()
            if self._config.verbose > 1:
                print(f"Deleted {path}")
            skip = True
        elif not path.exists():
            if self._config.verbose > 1:
                print(f"{path} not found.")
            skip = True

        for ignore_glob in self._config.ignore:
            if path.match(ignore_glob):
                skip = True
                break

        return skip

    def _is_older_than_timestamp(
        self,
        path: Path,
        timestamps: Optional[Timestamps],
        container_mtime: Optional[float],
    ) -> bool:
        """Is the file older than the timestamp."""
        # if the file is in an container, use the container time.
        # This helps if you have a new container that you
        # collected from someone who put really old files in it that
        # should still be optimised
        if container_mtime is not None:
            mtime = container_mtime
        else:
            mtime = path.stat().st_mtime

        # The timestamp or configured walk after time for comparison.
        walk_after = None
        if self._config.after is not None:
            walk_after = self._config.after
        elif container_mtime is None and timestamps:
            walk_after = timestamps.get(path)

        if walk_after is None:
            return False

        return bool(mtime <= walk_after)

    def walk_file(
        self,
        path: Path,
        timestamps: Optional[Timestamps],
        container_mtime: Optional[float] = None,
    ) -> Union[AsyncResult, DirResult, None]:
        """Optimize an individual file."""
        result: Union[AsyncResult, DirResult, None] = None
        try:
            if self._is_skippable(path):
                return result

            if path.is_dir():
                if self._config.recurse or container_mtime is not None:
                    result = self.walk_dir(path, timestamps, container_mtime)
                return result

            if self._is_older_than_timestamp(path, timestamps, container_mtime):
                return result

            handler = create_handler(self._config, path)

            if handler is None:
                return result

            if self._config.list_only:
                print(f"{path}: {handler.__class__.__name__}")
                return result

            if isinstance(handler, ContainerHandler):
                result = self._pool.apply_async(handler.unpack)
            elif isinstance(handler, ImageHandler):
                result = self._pool.apply_async(handler.optimize_image)
            else:
                raise ValueError(f"bad handler {handler}")
        except Exception as exc:
            result = self._pool.apply_async(ReportStats, args=(path, None, exc))
        return result

    def walk_dir(
        self,
        dir_path: Path,
        timestamps: Optional[Timestamps],
        container_mtime: Optional[float] = None,
    ) -> DirResult:
        """Recursively optimize a directory."""
        dir_result = DirResult(dir_path, [])
        for root, _, filenames in os.walk(dir_path):
            root_path = Path(root)
            for filename in sorted(filenames):
                full_path = root_path / filename
                result = self.walk_file(full_path, timestamps, container_mtime)
                if result:
                    dir_result.results.append(result)

        return dir_result

    def _walk_container_dir(
        self, handler: ContainerHandler
    ) -> Union[ContainerDirResult, AsyncResult]:
        """Optimize a container."""
        result: Union[ContainerDirResult, AsyncResult]
        try:
            container_mtime = handler.original_path.stat().st_mtime
            dir_result = self.walk_dir(
                handler.tmp_container_dir,
                None,
                container_mtime,
            )
            result = ContainerDirResult(handler.final_path, dir_result.results, handler)
        except Exception as exc:
            args = tuple([exc])
            result = self._pool.apply_async(handler.error, args=args)
        return result

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

    def _report_totals(self, totals: Totals) -> None:
        """Report the total number and percent of bytes saved."""
        if totals.bytes_in:
            bytes_saved = totals.bytes_in - totals.bytes_out
            percent_bytes_saved = bytes_saved / totals.bytes_in * 100
            msg = ""
            if self._config.test:
                if percent_bytes_saved > 0:
                    msg += "Could save"
                elif percent_bytes_saved == 0:
                    msg += "Could even out for"
                else:
                    msg += "Could lose"
            else:
                if percent_bytes_saved > 0:
                    msg += "Saved"
                elif percent_bytes_saved == 0:
                    msg += "Evened out"
                else:
                    msg = "Lost"
            msg += " a total of {} or {:.{prec}f}%".format(
                naturalsize(bytes_saved), percent_bytes_saved, prec=2
            )
            if self._config.verbose:
                print(msg)
                if self._config.test:
                    print("Test run did not change any files.")

        else:
            if self._config.verbose:
                print("Didn't optimize any files.")

        if totals.errors:
            print("Errors with the following files:")
            for rs in totals.errors:
                rs.report(self._config.test)

    def _handle_queue_item(
        self,
        timestamps: Timestamps,
        totals: Totals,
    ):
        queue: SimpleQueue = self.queues[timestamps]
        item: Union[
            ContainerHandler, DirResult, ContainerRepackResult, AsyncResult
        ] = queue.get()
        if isinstance(item, ContainerHandler):
            container_res = self._walk_container_dir(item)
            queue.put(container_res)
        elif isinstance(item, DirResult):
            for dir_member_result in item.results:
                # Put all the directory results on the queue
                queue.put(dir_member_result)
            if isinstance(item, ContainerDirResult):
                task = ContainerRepackResult(item.handler)
                queue.put(task)
            else:
                # Dump timestamps after every directory completes
                if self._should_record_timestamp(item.path):
                    timestamps.set(item.path, compact=True)
                    timestamps.dump_timestamps()
        elif isinstance(item, ContainerRepackResult):
            repack_result = self._pool.apply_async(item.handler.repack)
            queue.put(repack_result)
        elif isinstance(item, AsyncResult):
            res = item.get()
            if not isinstance(item, ReportStats):
                queue.put(res)
            elif res.error:
                print(res.error)
                totals.errors.append(res)
            else:
                if self._should_record_timestamp(res.path):
                    timestamps.set(res.path)
                totals.bytes_in += res.bytes_in
                totals.bytes_out += res.bytes_out

    def _get_timestamps_config(self) -> Dict[str, Any]:
        """Create a timestamps config dict."""
        timestamps_config: Dict[str, Any] = {}
        for key in TIMESTAMPS_CONFIG_KEYS:
            timestamps_config[key] = self._config.get(key)
        return timestamps_config

    def _set_timestamps(self, path: Path, timestamps_config: Dict[str, Any]):
        dirpath = Timestamps.dirpath(path)
        if dirpath in self._timestamps:
            return
        timestamps = Timestamps(
            PROGRAM_NAME,
            dirpath,
            verbose=self._config.verbose,
            config=timestamps_config,
        )
        migrate_timestamps(timestamps, dirpath)
        self._timestamps[dirpath] = timestamps

    def run(self) -> bool:
        """Optimize all configured files."""
        if not self._top_paths:
            print("No paths to optimize.")
            return False

        # Init timestamps.
        timestamps_config = self._get_timestamps_config()
        for top_path in self._top_paths:
            if not top_path.exists():
                print(f"Path does not exist: {top_path}")
                return False
            self._set_timestamps(top_path, timestamps_config)
        self.timestamps_filename = next(iter(self._timestamps.values())).filename

        print("Optimizing formats:", *sorted(self._config.formats))
        if self._config.after is not None and self._config.verbose:
            print("Optimizing after", time.ctime(self._config.after))

        # Fire off all async processes using a queue per timestamps file.
        self.queues: Dict[Timestamps, SimpleQueue[Any]] = {}
        totals = Totals()
        for top_path in self._top_paths:
            timestamps = self._get_timestamps(top_path)
            if timestamps not in self.queues:
                self.queues[timestamps] = SimpleQueue()
            queue = self.queues[timestamps]
            result = self.walk_file(top_path, timestamps)
            queue.put(result)

        # Process each queue
        for timestamps, queue in self.queues.items():
            while not queue.empty():
                self._handle_queue_item(timestamps, totals)

        # Finish by reporting totals
        self._report_totals(totals)

        # Shut down multiprocessing
        self._pool.close()
        self._pool.join()

        return True
