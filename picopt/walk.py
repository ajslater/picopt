"""Walk the directory trees and files and call the optimizers."""
import os
import shutil
import traceback
from multiprocessing.pool import ApplyResult, Pool
from pathlib import Path
from types import MappingProxyType

from confuse.templates import AttrDict
from termcolor import cprint
from treestamps import Grovestamps, GrovestampsConfig, Treestamps

from picopt import PROGRAM_NAME
from picopt.config import TIMESTAMPS_CONFIG_KEYS
from picopt.exceptions import PicoptError
from picopt.handlers.container import ContainerHandler
from picopt.handlers.factory import create_handler
from picopt.handlers.handler import Handler
from picopt.handlers.image import ImageHandler
from picopt.old_timestamps import OLD_TIMESTAMPS_NAME, OldTimestamps
from picopt.path import PathInfo, is_path_ignored
from picopt.stats import ReportStats, Totals


class Walk:
    """Walk object for storing state of a walk run."""

    TIMESTAMPS_FILENAMES = frozenset(
        {*Treestamps.get_filenames(PROGRAM_NAME), OLD_TIMESTAMPS_NAME}
    )
    LOWERCASE_TESTNAME = ".picopt_case_sensitive_test"
    UPPERCASE_TESTNAME = LOWERCASE_TESTNAME.upper()

    ########
    # Init #
    ########
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
            raise PicoptError(msg)
        for path in self._top_paths:
            if not path.exists():
                msg = f"Path does not exist: {path}"
                raise PicoptError(msg)

        # Init timestamps
        if self._config.timestamps:
            self._init_run_timestamps()

    ############
    # Checkers #
    ############
    def _is_skippable(self, path_info: PathInfo) -> bool:
        """Handle things that are not optimizable files."""
        reason = None
        color = "white"
        attrs: list = ["dark"]

        # File types
        if path_info.zipinfo and path_info.is_dir():
            reason = f"Skip archive directory {path_info.full_name()}"
        elif (
            not self._config.symlinks and path_info.path and path_info.path.is_symlink()
        ):
            reason = f"Skip symlink {path_info.full_name()}"
        elif path_info.name() in self.TIMESTAMPS_FILENAMES:
            legacy = "legacy " if path_info.name() == OLD_TIMESTAMPS_NAME else ""
            reason = f"Skip {legacy}timestamp {path_info.full_name()}"
        elif not path_info.zipinfo and path_info.path and not path_info.path.exists():
            reason = f"WARNING: {path_info.full_name()} not found."
            color = "yellow"
            attrs = []
        elif is_path_ignored(self._config, Path(path_info.name())):
            reason = f"Skip ignored {path_info.full_name()}"

        if reason and self._config.verbose > 1:
            cprint(reason, color, attrs=attrs)

        return bool(reason)

    def _is_older_than_timestamp(
        self,
        path_info: PathInfo,
    ) -> bool:
        """Is the file older than the timestamp."""
        if self._config.after is not None:
            walk_after = self._config.after
        elif self._config.timestamps:
            timestamps = self._timestamps.get(path_info.top_path, {})
            walk_after = timestamps.get(path_info.path)
        else:
            walk_after = None

        if walk_after is None:
            return False

        mtime = path_info.mtime()
        return bool(mtime <= walk_after)

    def _clean_up_working_files(self, path: Path) -> None:
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
        container_mtime: float | None,
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
                if final_result.saved > 0 and not self._config.bigger:
                    self._totals.bytes_out += final_result.bytes_out
                else:
                    self._totals.bytes_out += final_result.bytes_in
            if self._config.timestamps and not container_mtime:
                timestamps = self._timestamps[top_path]
                timestamps.set(final_result.path)

    def walk_dir(self, path_info: PathInfo) -> None:
        """Recursively optimize a directory."""
        if (
            not self._config.recurse
            or path_info.is_container_child()
            or not path_info.is_dir()
        ):
            # Skip
            return

        results = []
        files = []
        dir_path: Path = path_info.path  # type: ignore

        for name in sorted(os.listdir(dir_path)):
            entry_path = dir_path / name
            if entry_path.is_dir():
                path_info = PathInfo(
                    path_info.top_path,
                    path_info.container_mtime,
                    path_info.convert,
                    path_info.is_case_sensitive,
                    path=entry_path,
                )
                self.walk_file(path_info)
            else:
                files.append(entry_path)

        for entry_path in files:
            path_info = PathInfo(
                path_info.top_path,
                path_info.container_mtime,
                path_info.convert,
                path_info.is_case_sensitive,
                path=entry_path,
            )
            result = self.walk_file(path_info)
            if result:
                results.append(result)

        self._finish_results(
            results,
            path_info.container_mtime,
            path_info.top_path,
        )

        if self._config.timestamps:
            # Compact timestamps after every directory completes
            timestamps = self._timestamps[path_info.top_path]
            timestamps.set(dir_path, compact=True)

    def _walk_container(self, handler: ContainerHandler) -> ApplyResult:
        """Optimize a container."""
        result: ApplyResult
        try:
            for path_info in handler.unpack():
                container_result = self.walk_file(path_info)
                handler.set_task(path_info, container_result)

            handler.optimize_contents()

            # at this point handler_final_result array contains buffers not mp-results
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
        path_info: PathInfo,
    ) -> bool:
        """Decide on skip the file or not."""
        if self._is_skippable(path_info):
            if self._config.verbose == 1:
                cprint(".", "white", attrs=["dark"], end="")
            return True

        path = path_info.path
        if path and path.name.rfind(Handler.WORKING_SUFFIX) > -1:
            self._clean_up_working_files(path)
            if self._config.verbose == 1:
                cprint(".", "yellow", end="")
            return True
        return False

    def _handle_file(self, handler):
        """Call the correct walk or pool apply for the handler."""
        if isinstance(handler, ContainerHandler):
            # Unpack inline, not in the pool, and walk immediately like dirs.
            result = self._walk_container(handler)
        elif isinstance(handler, ImageHandler):
            result = self._pool.apply_async(handler.optimize_wrapper)
        else:
            msg = f"Bad picopt handler {handler}"
            raise TypeError(msg)
        return result

    def walk_file(self, path_info: PathInfo) -> ApplyResult | None:
        """Optimize an individual file."""
        try:
            if path_info.frame is None:
                if self._is_walk_file_skip(path_info):
                    return None

                if path_info.is_dir():
                    return self.walk_dir(path_info)

                if self._is_older_than_timestamp(path_info):
                    self._skip_older_than_timestamp(path_info)
                    return None

            handler = create_handler(self._config, path_info)
            if handler is None:
                return None

            if self._config.list_only:
                return None

            result = self._handle_file(handler)
        except Exception as exc:
            traceback.print_exc()
            apply_kwargs = MappingProxyType(
                {
                    "path": path_info.path,
                    "convert": path_info.convert,
                    "bytes_in": path_info.bytes_in(),
                    "test": self._config.test,
                    "exc": exc,
                }
            )
            result = self._pool.apply_async(ReportStats, (), apply_kwargs)
        return result

    ################
    # Init and run #
    ################
    def __init__(self, config: AttrDict) -> None:
        """Initialize."""
        self._config = config
        self._totals = Totals(config)
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
            path_info = PathInfo(dirpath, 0.0, True, is_case_sensitive, path=top_path)
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

        cprint("done.")

        if self._config.timestamps:
            self._timestamps.dump()

        return self._totals
