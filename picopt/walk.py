"""Walk the directory trees and files and call the optimizers."""
import os
import shutil
import time
import traceback
from multiprocessing.pool import ApplyResult, Pool
from pathlib import Path
from typing import Optional

from confuse.templates import AttrDict
from humanize import naturalsize
from termcolor import cprint
from treestamps import Grovestamps, GrovestampsConfig, Treestamps

from picopt import PROGRAM_NAME
from picopt.config import TIMESTAMPS_CONFIG_KEYS
from picopt.configurable import Configurable
from picopt.data import PathInfo, ReportInfo
from picopt.handlers.container import ContainerHandler
from picopt.handlers.factory import create_handler
from picopt.handlers.handler import Handler
from picopt.handlers.image import ImageHandler
from picopt.handlers.png import Png
from picopt.handlers.webp import WebP
from picopt.handlers.zip import CBR, Rar
from picopt.old_timestamps import OLD_TIMESTAMPS_NAME, OldTimestamps
from picopt.stats import ReportStats, Totals


class Walk(Configurable):
    """Walk object for storing state of a walk run."""

    TIMESTAMPS_FILENAMES = frozenset(Treestamps.get_filenames(PROGRAM_NAME))
    LOWERCASE_TESTNAME = ".picopt_case_sensitive_test"
    UPPERCASE_TESTNAME = LOWERCASE_TESTNAME.upper()

    ########
    # Init #
    ########
    def _convert_message(
        self, convert_from_formats: frozenset[str], convert_handler: type[Handler]
    ):
        convert_from = ", ".join(
            sorted(convert_from_formats & frozenset(self._config.formats))
        )
        convert_to = convert_handler.OUTPUT_FORMAT_STR
        cprint(f"Converting {convert_from} to {convert_to}", "cyan")

    def _init_run_verbose(self) -> None:
        """Print verbose init messages."""
        format_list = ", ".join(sorted(self._config.formats))
        cprint(f"Optimizing formats: {format_list}")
        if self._config.convert_to:
            if WebP.OUTPUT_FORMAT_STR in self._config.convert_to:
                self._convert_message(
                    self._config.computed.convertable_formats.webp, WebP
                )
            elif Png.OUTPUT_FORMAT_STR in self._config.convert_to:
                self._convert_message(
                    self._config.computed.convertable_formats.png, Png
                )
            if Rar.OUTPUT_FORMAT_STR in self._config.convert_to:
                self._convert_message(frozenset([Rar.INPUT_FORMAT_STR]), Rar)
            if CBR.OUTPUT_FORMAT_STR in self._config.convert_to:
                self._convert_message(frozenset([CBR.INPUT_FORMAT_STR]), CBR)
        if self._config.after is not None:
            after = time.ctime(self._config.after)
            cprint(f"Optimizing after {after}")

    def _init_run_timestamps(self) -> None:
        """Init timestamps."""
        config = GrovestampsConfig(
            paths=self._top_paths,
            program_name=PROGRAM_NAME,
            verbose=self._config.verbose,
            symlinks=self._config.symlinks,
            ignore=self._config.ignore,
            check_config=self._config.timestamps_check_config,
            program_config=self._config,
            program_config_keys=TIMESTAMPS_CONFIG_KEYS,
        )
        self._timestamps = Grovestamps(config)
        for timestamps in self._timestamps.values():
            OldTimestamps(self._config, timestamps).import_old_timestamps()

    def _init_run(self):
        """Init Run."""
        # Validate top_paths
        if not self._top_paths:
            msg = "No paths to optimize."
            raise ValueError(msg)
        for path in self._top_paths:
            if not path.exists():
                msg = f"Path does not exist: {path}"
                raise ValueError(msg)

        # Tell the user what we're doing
        if self._config.verbose:
            self._init_run_verbose()

        # Init timestamps
        if self._config.timestamps:
            self._init_run_timestamps()

    ############
    # Checkers #
    ############
    def _is_skippable(self, path: Path) -> bool:  # noqa C901
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
        elif path.name in OLD_TIMESTAMPS_NAME:
            if self._config.verbose > 1:
                cprint(f"Skip legacy timestamp {path}", "white", attrs=["dark"])
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
        info: PathInfo,
    ) -> bool:
        """Is the file older than the timestamp."""
        # If the file is in an container, use the container time.
        # This helps if you have a new container that you
        # collected from someone who put really old files in it that
        # should still be optimised
        mtime = (
            info.container_mtime
            if info.container_mtime is not None
            else info.path.stat().st_mtime
        )

        # The timestamp or configured walk after time for comparison.
        if self._config.after is not None:
            walk_after = self._config.after
        elif info.container_mtime is None and self._config.timestamps:
            timestamps = self._timestamps.get(info.top_path, {})
            walk_after = timestamps.get(info.path)
        else:
            walk_after = None

        if walk_after is None:
            return False

        return bool(mtime <= walk_after)

    def _clean_up_working_files(self, path) -> None:
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

    def walk_dir(self, info: PathInfo) -> None:
        """Recursively optimize a directory."""
        if not self._config.recurse and info.container_mtime is None:
            # Skip
            return

        results = []
        files = []
        for name in sorted(os.listdir(info.path)):
            entry_path = info.path / name
            if entry_path.is_dir():
                path_info = PathInfo(
                    entry_path,
                    info.top_path,
                    info.container_mtime,
                    info.convert,
                    info.is_case_sensitive,
                )
                self.walk_file(path_info)
            else:
                files.append(entry_path)

        for entry_path in files:
            path_info = PathInfo(
                entry_path,
                info.top_path,
                info.container_mtime,
                info.convert,
                info.is_case_sensitive,
            )
            result = self.walk_file(path_info)
            if result:
                results.append(result)

        self._finish_results(
            results,
            info.container_mtime,
            info.top_path,
        )

        if self._config.timestamps and not info.container_mtime:
            # Compact timestamps after every directory completes
            timestamps = self._timestamps[info.top_path]
            timestamps.set(info.path, compact=True)

    def _walk_container(
        self, top_path: Path, handler: ContainerHandler, is_case_sensitive: bool
    ) -> ApplyResult:
        """Optimize a container."""
        result: ApplyResult
        try:
            handler.unpack()
            container_mtime = handler.original_path.stat().st_mtime
            path_info = PathInfo(
                handler.tmp_container_dir,
                top_path,
                container_mtime,
                handler.CONVERT,
                is_case_sensitive,
            )

            self.walk_dir(path_info)
            result = self._pool.apply_async(handler.repack)
        except Exception as exc:
            traceback.print_exc()
            args = (exc,)
            result = self._pool.apply_async(handler.error, args=args)
        return result

    def _skip_older_than_timestamp(self, path) -> None:
        """Report on skipping files older than the timestamp."""
        color = "green"
        if self._config.verbose == 1:
            cprint(".", color, end="")
        elif self._config.verbose > 1:
            cprint(f"Skip older than timestamp: {path}", color)

    def _is_walk_file_skip(
        self,
        info: PathInfo,
    ) -> bool:
        """Decide on skip the file or not."""
        if self._is_skippable(info.path):
            if self._config.verbose == 1:
                cprint(".", "white", attrs=["dark"], end="")
            return True

        if info.path.name.rfind(Handler.WORKING_SUFFIX) > -1:
            self._clean_up_working_files(info.path)
            if self._config.verbose == 1:
                cprint(".", "yellow", end="")
            return True
        return False

    def _handle_file(self, handler, top_path, is_case_sensitive):
        """Call the correct walk or pool apply for the handler."""
        if isinstance(handler, ContainerHandler):
            # Unpack inline, not in the pool, and walk immediately like dirs.
            result = self._walk_container(top_path, handler, is_case_sensitive)
        elif isinstance(handler, ImageHandler):
            result = self._pool.apply_async(handler.optimize_image)
        else:
            msg = f"bad handler {handler}"
            raise TypeError(msg)
        return result

    def walk_file(self, info: PathInfo) -> Optional[ApplyResult]:
        """Optimize an individual file."""
        try:
            if self._is_walk_file_skip(info):
                return None

            if info.path.is_dir():
                return self.walk_dir(info)

            if self._is_older_than_timestamp(info):
                self._skip_older_than_timestamp(info.path)
                return None

            handler = create_handler(self._config, info)
            if handler is None:
                return None

            if self._config.list_only:
                return None

            result = self._handle_file(handler, info.top_path, info.is_case_sensitive)
        except Exception as exc:
            traceback.print_exc()
            report_info = ReportInfo(
                path=info.path,
                convert=info.convert,
                test=self._config.test,
                exc=exc,
            )
            result = self._pool.apply_async(ReportStats, (report_info,))
        return result

    ##########
    # Finish #
    ##########
    def _report_totals_bytes_in(self) -> None:
        """Report Totals if there were bytes in."""
        if not self._config.verbose and not self._config.test:
            return
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
        elif percent_bytes_saved > 0:
            msg += "Saved"
        elif percent_bytes_saved == 0:
            msg += "Evened out"
        else:
            msg = "Lost"
        natural_saved = naturalsize(bytes_saved)
        msg += f" a total of {natural_saved} or {percent_bytes_saved:.2f}%"
        cprint(msg)
        if self._config.test:
            cprint("Test run did not change any files.")

    def _report_totals(self) -> None:
        """Report the total number and percent of bytes saved."""
        if self._config.verbose == 1:
            cprint("")
        if self._totals.bytes_in:
            self._report_totals_bytes_in()
        elif self._config.verbose:
            cprint("Didn't optimize any files.")

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
        paths: list[Path] = sorted(frozenset(self._config.paths))
        for path in paths:
            if path.is_symlink() and not self._config.symlinks:
                continue
            top_paths.append(path)
        self._top_paths: tuple[Path, ...] = tuple(top_paths)
        if self._config.jobs:
            self._pool = Pool(self._config.jobs)
        else:
            self._pool = Pool()

    @classmethod
    def _is_case_sensitive(cls, dirpath: Path) -> bool:
        """Determine if a path is on a case sensitive filesystem."""
        lowercase_path = dirpath / cls.LOWERCASE_TESTNAME
        result = False
        try:
            lowercase_path.touch()
            uppercase_path = dirpath / cls.UPPERCASE_TESTNAME
            result = not uppercase_path.exists()
        finally:
            lowercase_path.unlink(missing_ok=True)
        return result

    def run(self) -> Totals:
        """Optimize all configured files."""
        self._init_run()

        # Walk each top file
        top_results = {}
        for top_path in self._top_paths:
            dirpath = Treestamps.get_dir(top_path)
            is_case_sensitive = self._is_case_sensitive(dirpath)
            path_info = PathInfo(top_path, dirpath, None, True, is_case_sensitive)
            result = self.walk_file(path_info)
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
            self._timestamps.dump()

        # Finish by reporting totals
        self._report_totals()
        return self._totals
