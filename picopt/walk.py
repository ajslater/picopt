"""Walk the directory trees and files and call the optimizers."""
import shutil
import time
import traceback

from multiprocessing.pool import ApplyResult, Pool
from pathlib import Path
from queue import SimpleQueue
from typing import Any, Optional, Type, Union

from confuse.templates import AttrDict
from humanize import naturalsize
from termcolor import cprint
from treestamps import Treestamps

from picopt import PROGRAM_NAME
from picopt.config import (
    PNG_CONVERTABLE_FORMATS,
    TIMESTAMPS_CONFIG_KEYS,
    WEBP_CONVERTABLE_FORMATS,
)
from picopt.handlers.container import ContainerHandler
from picopt.handlers.factory import create_handler
from picopt.handlers.handler import Handler
from picopt.handlers.image import TIFF_FORMAT, ImageHandler
from picopt.handlers.png import Png
from picopt.handlers.webp import WebP
from picopt.handlers.zip import CBZ, Zip
from picopt.old_timestamps import OldTimestamps
from picopt.stats import ReportStats
from picopt.tasks import (
    CompleteContainerTask,
    CompleteDirTask,
    CompleteTask,
    ContainerResult,
    DirResult,
    Totals,
)


class Walk:
    """Walk object for storing state of a walk run."""

    TIMESTAMPS_FILENAMES = set(Treestamps.get_filenames(PROGRAM_NAME))

    def __init__(self, config: AttrDict) -> None:
        """Initialize."""
        self._config: AttrDict = config
        top_paths = []
        for path in sorted(set(self._config.paths)):
            if path.is_symlink() and not self._config.symlinks:
                continue
            top_paths.append(path)
        self._top_paths: tuple[Path, ...] = tuple(top_paths)
        self._timestamps: dict[Path, Treestamps] = {}
        self._queues: dict[Path, SimpleQueue[Any]] = {}
        if self._config.jobs:
            self._pool = Pool(self._config.jobs)
        else:
            self._pool = Pool()

    def _is_skippable(self, path: Path) -> bool:
        """Handle things that are not optimizable files."""
        # File types
        if not self._config.symlinks and path.is_symlink():
            if self._config.verbose > 1:
                cprint(f"Skip symlink {path}", "white", attrs=["dark"])
            return True
        elif path.name in self.TIMESTAMPS_FILENAMES:
            return True
        elif not path.exists():
            if self._config.verbose > 1:
                cprint(f"WARNING: {path} not found.", "yellow")
            return True

        skip = False
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
            walk_after = self._timestamps.get(top_path, {}).get(path)

        if walk_after is None:
            return False

        return bool(mtime <= walk_after)

    def _clean_up_working_files(self, path):
        """Auto-clean old working temp files if encountered."""
        try:
            shutil.rmtree(path, ignore_errors=True)
            if self._config.verbose > 1:
                print(f"Deleted {path}")
        except Exception as exc:
            cprint(str(exc), "red")

    def walk_file(
        self,
        path: Path,
        top_path: Path,
        container_mtime: Optional[float] = None,
        convert: bool = True,
    ) -> Union[ApplyResult, DirResult, None]:
        """Optimize an individual file."""
        result: Union[ApplyResult, DirResult, None] = None
        try:
            if self._is_skippable(path):
                return result

            if path.name.rfind(Handler.WORKING_SUFFIX) > -1:
                self._clean_up_working_files(path)
                return result

            if path.is_dir():
                if self._config.recurse or container_mtime is not None:
                    result = self.walk_dir(
                        path, top_path, container_mtime, convert=convert
                    )
                return result

            if self._is_older_than_timestamp(path, top_path, container_mtime):
                return result

            handler = create_handler(self._config, path, convert=convert)

            if handler is None:
                return result

            if self._config.list_only:
                print(f"{path}: {handler.__class__.__name__}")
                return result

            if isinstance(handler, ContainerHandler):
                # Unpack inline, not in the pool, and walk immediately like dirs.
                handler.unpack()
                result = self._walk_container_dir(top_path, handler)
            elif isinstance(handler, ImageHandler):
                result = self._pool.apply_async(handler.optimize_image)
            else:
                raise ValueError(f"bad handler {handler}")
        except Exception as exc:
            traceback.print_exc()

            result = self._pool.apply_async(ReportStats, args=(path, None, exc))
        return result

    def walk_dir(
        self,
        dir_path: Path,
        top_path: Path,
        container_mtime: Optional[float] = None,
        convert: bool = True,
    ) -> DirResult:
        """Recursively optimize a directory."""
        dir_result = DirResult(dir_path, [])
        for path in dir_path.iterdir():
            result = self.walk_file(path, top_path, container_mtime, convert=convert)
            dir_result.results.append(result)

        return dir_result

    def _walk_container_dir(
        self, top_path: Path, handler: ContainerHandler
    ) -> Union[ContainerResult, ApplyResult]:
        """Optimize a container."""
        result: Union[ContainerResult, ApplyResult]
        try:
            container_mtime = handler.original_path.stat().st_mtime
            dir_result = self.walk_dir(
                handler.tmp_container_dir,
                top_path,
                container_mtime,
                convert=handler.CONVERT,
            )
            result = ContainerResult(handler.final_path, dir_result.results, handler)
        except Exception as exc:
            args = tuple([exc])
            result = self._pool.apply_async(handler.error, args=args)
        return result

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
            cprint("Errors with the following files:", "yellow")
            for rs in totals.errors:
                rs.report(self._config.test, "yellow")

    def _handle_queue_item_dir(self, top_path: Path, dir_result: DirResult):
        """Reverse the results tree to handle directories bottom up."""
        queue = self._queues[top_path]
        for dir_member_result in dir_result.results:
            if isinstance(dir_member_result, DirResult):
                self._handle_queue_item_dir(top_path, dir_member_result)
            else:
                queue.put(dir_member_result)
        if isinstance(dir_result, ContainerResult):
            task = CompleteContainerTask(dir_result.handler)
        else:
            task = CompleteDirTask(dir_result.path)
        queue.put(task)

    def _handle_queue_complete_task(self, top_path: Path, task: CompleteTask):
        if isinstance(task, CompleteDirTask):
            if self._config.timestamps:
                # Compact timestamps after every directory completes
                timestamps = self._timestamps[top_path]
                timestamps.set(task.path, compact=True)
        elif isinstance(task, CompleteContainerTask):
            # Repack inline, not in pool, to complete directories immediately
            repack_result = task.handler.repack()
            self._queues[top_path].put(repack_result)
        else:
            cprint(f"WARNING: Unhandled Complete task {task}", "yellow")

    def _handle_queue_item(
        self,
        top_path: Path,
        totals: Totals,
    ):
        queue: SimpleQueue = self._queues[top_path]
        item = queue.get()
        if isinstance(item, ApplyResult):
            # unpack apply results inline to preserve directory order
            item = item.get()

        if item is None:
            pass
        elif isinstance(item, ReportStats):
            if item.error:
                cprint(item.error, "yellow")
                totals.errors.append(item)
            else:
                if self._config.timestamps:
                    timestamps = self._timestamps[top_path]
                    timestamps.set(item.path)
                totals.bytes_in += item.bytes_in
                totals.bytes_out += item.bytes_out
        elif isinstance(item, DirResult):
            self._handle_queue_item_dir(top_path, item)
        elif isinstance(item, CompleteTask):
            self._handle_queue_complete_task(top_path, item)
        else:
            cprint(f"Unhandled queue item {item}", "yellow")

    def _convert_message(
        self, convert_from_formats: frozenset[str], convert_handler: Type[Handler]
    ):
        convert_from = ", ".join(
            sorted(convert_from_formats & frozenset(self._config.formats))
        )
        convert_to = convert_handler.OUTPUT_FORMAT
        cprint(f"Converting {convert_from} to {convert_to}", "cyan")

    def _get_covertable_formats(
        self, convertable_formats: frozenset[str]
    ) -> frozenset[str]:
        formats = set(convertable_formats)
        if TIFF_FORMAT in self._config.formats:
            formats.add(TIFF_FORMAT)
        return frozenset(formats)

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
                    formats = self._get_covertable_formats(WEBP_CONVERTABLE_FORMATS)
                    self._convert_message(formats, WebP)
                elif Png.OUTPUT_FORMAT in self._config.convert_to:
                    formats = self._get_covertable_formats(PNG_CONVERTABLE_FORMATS)
                    self._convert_message(formats, Png)
                if Zip.OUTPUT_FORMAT in self._config.convert_to:
                    self._convert_message(frozenset([Zip.INPUT_FORMAT_RAR]), Zip)
                if CBZ.OUTPUT_FORMAT in self._config.convert_to:
                    self._convert_message(frozenset([CBZ.INPUT_FORMAT_RAR]), CBZ)
            if self._config.after is not None:
                print("Optimizing after", time.ctime(self._config.after))

        # Init timestamps
        if self._config.timestamps:
            self._timestamps = Treestamps.path_to_treestamps_map_factory(
                self._top_paths,
                PROGRAM_NAME,
                self._config.verbose,
                self._config,
                TIMESTAMPS_CONFIG_KEYS,
            )
            for timestamps in self._timestamps.values():
                OldTimestamps(timestamps).import_old_timestamps()

    def run(self) -> bool:
        """Optimize all configured files."""
        try:
            self._init_run()
        except Exception as exc:
            cprint(str(exc), "red")
            return False

        # Start each queue
        totals = Totals()
        for top_path in self._top_paths:
            dirpath = Treestamps.dirpath(top_path)
            result = self.walk_file(top_path, dirpath)
            if dirpath not in self._queues:
                self._queues[dirpath] = SimpleQueue()
            queue = self._queues[dirpath]
            self._queues[dirpath].put(result)

        # Process each queue
        for top_path, queue in self._queues.items():
            while not queue.empty():
                self._handle_queue_item(top_path, totals)

        # Shut down multiprocessing
        self._pool.close()
        self._pool.join()

        if self._config.timestamps:
            for timestamps in self._timestamps.values():
                timestamps.dump()
        # Finish by reporting totals
        self._report_totals(totals)
        return True
