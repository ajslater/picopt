"""Walk the directory trees and files and call the optimizers."""
import os
import shutil
import time
import traceback

from multiprocessing.pool import ApplyResult, Pool
from pathlib import Path
from typing import Optional, Type

from confuse.templates import AttrDict
from humanize import naturalsize
from termcolor import cprint
from treestamps import Treestamps

from picopt import PROGRAM_NAME
from picopt.config import TIMESTAMPS_CONFIG_KEYS
from picopt.configurable import Configurable
from picopt.handlers.container import ContainerHandler
from picopt.handlers.factory import create_handler
from picopt.handlers.handler import Handler
from picopt.handlers.image import ImageHandler
from picopt.handlers.png import Png
from picopt.handlers.webp import WebP
from picopt.handlers.zip import CBZ, Zip
from picopt.old_timestamps import OldTimestamps
from picopt.stats import ReportStats, Totals


class Walk(Configurable):
    """Walk object for storing state of a walk run."""

    TIMESTAMPS_FILENAMES = set(Treestamps.get_filenames(PROGRAM_NAME))

    ########
    # Init #
    ########
    def _convert_message(
        self, convert_from_formats: frozenset[str], convert_handler: Type[Handler]
    ):
        convert_from = ", ".join(
            sorted(convert_from_formats & frozenset(self._config.formats))
        )
        convert_to = convert_handler.OUTPUT_FORMAT
        cprint(f"Converting {convert_from} to {convert_to}", "cyan")

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
                    self._convert_message(self._config._convertable_formats.webp, WebP)
                elif Png.OUTPUT_FORMAT in self._config.convert_to:
                    self._convert_message(self._config._convertable_formats.png, Png)
                if Zip.OUTPUT_FORMAT in self._config.convert_to:
                    self._convert_message(frozenset([Zip.INPUT_FORMAT_RAR]), Zip)
                if CBZ.OUTPUT_FORMAT in self._config.convert_to:
                    self._convert_message(frozenset([CBZ.INPUT_FORMAT_RAR]), CBZ)
            if self._config.after is not None:
                print("Optimizing after", time.ctime(self._config.after))

        # Init timestamps
        if self._config.timestamps:
            self._timestamps = Treestamps.map_factory(
                self._top_paths,
                PROGRAM_NAME,
                self._config.verbose,
                self._config.symlinks,
                self._config.ignore,
                self._config,
                TIMESTAMPS_CONFIG_KEYS,
            )
            for timestamps in self._timestamps.values():
                OldTimestamps(self._config, timestamps).import_old_timestamps()

    ############
    # Checkers #
    ############
    def _is_skippable(self, path: Path) -> bool:
        """Handle things that are not optimizable files."""
        skip = False
        # File types
        if not self._config.symlinks and path.is_symlink():
            if self._config.verbose > 1:
                cprint(f"Skip symlink {path}", "white", attrs=["dark"])
            skip = True
        elif path.name in self.TIMESTAMPS_FILENAMES:
            if self._config.verbose > 1:
                cprint(f"Skip timestamp {path}", "white", attrs=["dark"])
            skip = True
        elif not path.exists():
            if self._config.verbose > 1:
                cprint(f"WARNING: {path} not found.", "yellow")
            skip = True
        elif self.is_path_ignored(path):
            if self._config.verbose > 1:
                cprint(f"Skip ignored {path}", "white", attrs=["dark"])
            skip = True

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
            timestamps = self._timestamps.get(top_path, {})
            walk_after = timestamps.get(path)

        if walk_after is None:
            return False

        return bool(mtime <= walk_after)

    def _clean_up_working_files(self, path):
        """Auto-clean old working temp files if encountered."""
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
            if self._config.verbose > 1:
                cprint(f"Deleted {path}", "yellow")
        except Exception as exc:
            cprint(str(exc), "red")

    ###########
    # Walkers #
    ###########
    def _finish_results(
        self,
        results: list[ApplyResult],
        container_mtime: Optional[float],
        top_path: Path,
    ) -> None:
        """Get the async results and total them."""
        for result in results:
            final_result = result.get()
            if final_result.exc:
                final_result.report()
                self._totals.errors.append(final_result)
            else:
                self._totals.bytes_in += final_result.bytes_in
                self._totals.bytes_out += final_result.bytes_out
            if self._config.timestamps and not container_mtime:
                timestamps = self._timestamps[top_path]
                timestamps.set(final_result.path)

    def walk_dir(
        self,
        path: Path,
        top_path: Path,
        container_mtime: Optional[float],
        convert: bool,
    ) -> None:
        """Recursively optimize a directory."""
        results = []
        files = []
        for name in sorted(os.listdir(path)):
            entry_path = path / name
            if entry_path.is_dir():
                self.walk_file(entry_path, top_path, container_mtime, convert)
            else:
                files.append(entry_path)

        for entry_path in files:
            result = self.walk_file(entry_path, top_path, container_mtime, convert)
            if result:
                results.append(result)

        self._finish_results(
            results,
            container_mtime,
            top_path,
        )

        if self._config.timestamps and not container_mtime:
            # Compact timestamps after every directory completes
            timestamps = self._timestamps[top_path]
            timestamps.set(path, compact=True)

    def _walk_container(self, top_path: Path, handler: ContainerHandler) -> ApplyResult:
        """Optimize a container."""
        result: ApplyResult
        try:
            handler.unpack()
            container_mtime = handler.original_path.stat().st_mtime
            self.walk_dir(
                handler.tmp_container_dir,
                top_path,
                container_mtime,
                handler.CONVERT,
            )
            result = self._pool.apply_async(handler.repack)
        except Exception as exc:
            traceback.print_exc()
            args = tuple([exc])
            result = self._pool.apply_async(handler.error, args=args)
        return result

    def walk_file(
        self,
        path: Path,
        top_path: Path,
        container_mtime: Optional[float],
        convert: bool,
    ) -> Optional[ApplyResult]:
        """Optimize an individual file."""
        result: Optional[ApplyResult] = None
        try:
            # START DECIDE
            if self._is_skippable(path):
                if self._config.verbose == 1:
                    cprint(".", "white", attrs=["dark"], end="")
                return result

            if path.name.rfind(Handler.WORKING_SUFFIX) > -1:
                self._clean_up_working_files(path)
                if self._config.verbose == 1:
                    cprint(".", "yellow", end="")
                return result

            if path.is_dir():
                if self._config.recurse or container_mtime is not None:
                    result = self.walk_dir(path, top_path, container_mtime, convert)
                return result

            if self._is_older_than_timestamp(path, top_path, container_mtime):
                color = "green"
                if self._config.verbose == 1:
                    cprint(".", color, end="")
                elif self._config.verbose > 1:
                    cprint(f"Skip older than timestamp: {path}", color)
                return result
            # END DECIDE

            handler = create_handler(self._config, path, convert=convert)

            if handler is None:
                return result

            if self._config.list_only:
                print(f"{path}: {handler.__class__.__name__}")
                return result

            if isinstance(handler, ContainerHandler):
                # Unpack inline, not in the pool, and walk immediately like dirs.
                result = self._walk_container(top_path, handler)
            elif isinstance(handler, ImageHandler):
                result = self._pool.apply_async(handler.optimize_image)
            else:
                raise ValueError(f"bad handler {handler}")
        except Exception as exc:
            traceback.print_exc()
            result = self._pool.apply_async(
                ReportStats, args=(path, None, self._config.test, convert, exc)
            )
        return result

    ##########
    # Finish #
    ##########
    def _report_totals(self) -> None:
        """Report the total number and percent of bytes saved."""
        if self._config.verbose == 1:
            print()
        if self._totals.bytes_in:
            bytes_saved = self._totals.bytes_in - self._totals.bytes_out
            percent_bytes_saved = bytes_saved / self._totals.bytes_in * 100
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

        if self._totals.errors:
            cprint("Errors with the following files:", "red")
            for rs in self._totals.errors:
                rs.report()

    ################
    # Init and run #
    ################
    def __init__(self, config: AttrDict) -> None:
        """Initialize."""
        super().__init__(config)
        self._totals = Totals()
        top_paths = []
        for path in sorted(frozenset(self._config.paths)):
            if path.is_symlink() and not self._config.symlinks:
                continue
            top_paths.append(path)
        self._top_paths: tuple[Path, ...] = tuple(top_paths)
        self._timestamps: dict[Path, Treestamps] = {}
        if self._config.jobs:
            self._pool = Pool(self._config.jobs)
        else:
            self._pool = Pool()

    def run(self) -> bool:
        """Optimize all configured files."""
        try:
            self._init_run()
        except Exception as exc:
            cprint(str(exc), "red")
            return False

        # Walk each top file
        top_results = {}
        for top_path in self._top_paths:
            dirpath = Treestamps.dirpath(top_path)
            result = self.walk_file(top_path, dirpath, None, True)
            if not result:
                continue
            if dirpath not in top_results:
                top_results[dirpath] = []
            top_results[dirpath].append(result)

        # Finish
        for dirpath, results in top_results.items():
            self._finish_results(results, None, dirpath)

        # Shut down multiprocessing
        self._pool.close()
        self._pool.join()

        if self._config.timestamps:
            for top_path, timestamps in self._timestamps.items():
                if self._config.verbose:
                    print(f"\nSaving timestamps for {top_path}")
                timestamps.dump()

        # Finish by reporting totals
        self._report_totals()
        return True
