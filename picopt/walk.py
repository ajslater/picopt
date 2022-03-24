"""Walk the directory trees and files and call the optimizers."""
import time

from multiprocessing.pool import ApplyResult, Pool
from pathlib import Path
from queue import SimpleQueue
from typing import Any, Optional, Sequence, Type, Union

from confuse.templates import AttrDict
from humanize import naturalsize

from picopt import PROGRAM_NAME
from picopt.config import (
    PNG_CONVERTABLE_FORMATS,
    TIMESTAMPS_CONFIG_KEYS,
    WEBP_CONVERTABLE_FORMATS,
)
from picopt.handlers.container import ContainerHandler
from picopt.handlers.factory import create_handler
from picopt.handlers.handler import Handler
from picopt.handlers.image import ImageHandler
from picopt.handlers.png import Png
from picopt.handlers.webp import WebP
from picopt.handlers.zip import CBZ, Zip
from picopt.old_timestamps import OldTimestamps
from picopt.stats import ReportStats
from picopt.tasks import (
    ContainerDirResult,
    ContainerRepackResult,
    DirCompactTask,
    DirResult,
    Totals,
)
from picopt.timestamps import Timestamps


class Walk:
    """Walk object for storing state of a walk run."""

    @staticmethod
    def dirpath(path: Path):
        """Return a directory for a path."""
        return path if path.is_dir() else path.parent

    def __init__(self, config: AttrDict) -> None:
        """Initialize."""
        self._config: AttrDict = config
        config_paths: Sequence[Path] = self._config.paths
        self._top_paths: tuple[Path, ...] = tuple(sorted(set(config_paths)))
        self._timestamps: dict[Path, Timestamps] = {}
        if self._config.jobs:
            self._pool = Pool(self._config.jobs)
        else:
            self._pool = Pool()
        timestamps_filename = Timestamps.get_timestamps_filename(PROGRAM_NAME)
        timestamps_wal_filename = Timestamps.get_wal_filename(PROGRAM_NAME)
        self._timestamps_filenames = set([timestamps_filename, timestamps_wal_filename])
        self.queues: dict[Path, SimpleQueue[Any]] = {}

    def _is_skippable(self, path: Path) -> bool:
        """Handle things that are not optimizable files."""
        # File types
        skip = False
        if not self._config.follow_symlinks and path.is_symlink():
            if self._config.verbose > 1:
                print(f"Skip symlink {path}")
            skip = True
        elif path.name in self._timestamps_filenames:
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
        top_path: Path,
        container_mtime: Optional[float],
    ) -> bool:
        """Is the file older than the timestamp."""
        # If the file is in an container, use the container time.
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
        elif container_mtime is None:
            timestamps = self._timestamps.get(top_path)
            if timestamps:
                walk_after = timestamps.get(path)

        if walk_after is None:
            return False

        return bool(mtime <= walk_after)

    def walk_file(
        self,
        path: Path,
        top_path: Path,
        container_mtime: Optional[float] = None,
    ) -> Union[ApplyResult, DirResult, None]:
        """Optimize an individual file."""
        result: Union[ApplyResult, DirResult, None] = None
        try:
            if self._is_skippable(path):
                return result

            if path.is_dir():
                if self._config.recurse or container_mtime is not None:
                    result = self.walk_dir(path, top_path, container_mtime)
                return result

            if self._is_older_than_timestamp(path, top_path, container_mtime):
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
        top_path: Path,
        container_mtime: Optional[float] = None,
    ) -> DirResult:
        """Recursively optimize a directory."""
        dir_result = DirResult(dir_path, [])
        for path in dir_path.iterdir():
            result = self.walk_file(path, top_path, container_mtime)
            dir_result.results.append(result)

        return dir_result

    def _walk_container_dir(
        self, top_path: Path, handler: ContainerHandler
    ) -> Union[ContainerDirResult, ApplyResult]:
        """Optimize a container."""
        result: Union[ContainerDirResult, ApplyResult]
        try:
            container_mtime = handler.original_path.stat().st_mtime
            dir_result = self.walk_dir(
                handler.tmp_container_dir,
                top_path,
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
            self._config.timestamps
            and (self._config.follow_symlinks or not path.is_symlink())
            and path.exists()
            and Handler.WORKING_SUFFIX not in str(path)
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

    def _handle_queue_item_dir(self, top_path: Path, dir_result: DirResult):
        """Reverse the results tree to handle directories bottom up."""
        queue = self.queues[top_path]
        for dir_member_result in dir_result.results:
            if isinstance(dir_member_result, DirResult):
                self._handle_queue_item_dir(top_path, dir_member_result)
            else:
                queue.put(dir_member_result)
        if isinstance(dir_result, ContainerDirResult):
            task = ContainerRepackResult(dir_result.handler)
        else:
            task = DirCompactTask(dir_result.path)
        queue.put(task)

    def _handle_queue_item(
        self,
        top_path: Path,
        totals: Totals,
    ):
        queue: SimpleQueue = self.queues[top_path]
        item = queue.get()
        if isinstance(item, ApplyResult):
            # unpack apply results inline to preserve directory order
            item = item.get()

        if item is None:
            pass
        elif isinstance(item, ReportStats):
            if item.error:
                print(item.error)
                totals.errors.append(item)
            else:
                if self._should_record_timestamp(item.path):
                    self._timestamps[top_path].set(item.path)
                totals.bytes_in += item.bytes_in
                totals.bytes_out += item.bytes_out
        elif isinstance(item, ContainerHandler):
            container_res = self._walk_container_dir(top_path, item)
            queue.put(container_res)
        elif isinstance(item, DirResult):
            self._handle_queue_item_dir(top_path, item)
        elif isinstance(item, DirCompactTask):
            if self._should_record_timestamp(item.path):
                # Dump timestamps after every directory completes
                timestamps = self._timestamps[top_path]
                timestamps.set(item.path, compact=True)
                timestamps.dump_timestamps()
        elif isinstance(item, ContainerRepackResult):
            repack_result = self._pool.apply_async(item.handler.repack)
            queue.put(repack_result)
        else:
            print(f"Unhandled queue item {item}")

    def _set_timestamps(self, path: Path, timestamps_config: dict[str, Any]):
        """Read timestamps."""
        dirpath = self.dirpath(path)
        if dirpath in self._timestamps:
            return
        timestamps = Timestamps(
            PROGRAM_NAME,
            dirpath,
            verbose=self._config.verbose,
            config=timestamps_config,
        )
        OldTimestamps(timestamps).import_old_timestamps()
        self._timestamps[dirpath] = timestamps

    def _convert_message(
        self, convert_from_formats: frozenset[str], convert_handler: Type[Handler]
    ):
        convert_from = ", ".join(sorted(convert_from_formats))
        convert_to = convert_handler.OUTPUT_FORMAT
        print(f"Converting {convert_from} to {convert_to}")

    def _init_run(self):
        """Init Run."""
        # Validate top_paths
        if not self._top_paths:
            raise ValueError("No paths to optimize.")
        for path in self._top_paths:
            if not path.exists():
                raise ValueError(f"Path does not exist: {path}")

        # Tell the user what we're doing
        if self._config.verbose:
            print("Optimizing formats:", *sorted(self._config.formats))
            if self._config.convert_to:
                if WebP.OUTPUT_FORMAT in self._config.convert_to:
                    self._convert_message(WEBP_CONVERTABLE_FORMATS, WebP)
                elif Png.OUTPUT_FORMAT in self._config.convert_to:
                    self._convert_message(PNG_CONVERTABLE_FORMATS, Png)
                if Zip.OUTPUT_FORMAT in self._config.convert_to:
                    self._convert_message(frozenset([Zip.INPUT_FORMAT_RAR]), Zip)
                if CBZ.OUTPUT_FORMAT in self._config.convert_to:
                    self._convert_message(frozenset([CBZ.INPUT_FORMAT_RAR]), CBZ)
            if self._config.after is not None:
                print("Optimizing after", time.ctime(self._config.after))

        # Init timestamps
        if self._config.timestamps:
            timestamps_config: dict[str, Any] = {}
            for key in TIMESTAMPS_CONFIG_KEYS:
                timestamps_config[key] = self._config.get(key)
            for top_path in self._top_paths:
                self._set_timestamps(top_path, timestamps_config)

    def run(self) -> bool:
        """Optimize all configured files."""
        try:
            self._init_run()
        except Exception as exc:
            print(exc)
            return False

        # Start each queue
        totals = Totals()
        for top_path in self._top_paths:
            dirpath = self.dirpath(top_path)
            result = self.walk_file(top_path, dirpath)
            if dirpath not in self.queues:
                self.queues[dirpath] = SimpleQueue()
            queue = self.queues[dirpath]
            self.queues[dirpath].put(result)

        # Process each queue
        for top_path, queue in self.queues.items():
            while not queue.empty():
                self._handle_queue_item(top_path, totals)
            if self._should_record_timestamp(top_path):
                self._timestamps[top_path].dump_timestamps()

        # Shut down multiprocessing
        self._pool.close()
        self._pool.join()

        # Finish by reporting totals
        self._report_totals(totals)
        return True
