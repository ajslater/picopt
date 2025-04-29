"""Walk the directory trees and files and call the optimizers."""

import traceback
from multiprocessing.pool import ApplyResult
from pathlib import Path

from termcolor import cprint
from treestamps import Treestamps

from picopt.handlers.container import ContainerHandler
from picopt.handlers.handler import Handler
from picopt.handlers.image import ImageHandler
from picopt.path import PathInfo
from picopt.report import ReportStats, Totals
from picopt.walk.handler_factory import HandlerFactory


class Walk(HandlerFactory):
    """Methods for walking the tree and handling files."""

    def _finish_results(
        self,
        results: list[ApplyResult],
        top_path: Path,
    ) -> None:
        """Get the async results and total them."""
        for result in results:
            final_result = result.get()
            if final_result.exc:
                final_result.report(self._printer)

                self._totals.errors.append(final_result)
            else:
                self._totals.bytes_in += final_result.bytes_in
                if final_result.saved > 0 and not self._config.bigger:
                    self._totals.bytes_out += final_result.bytes_out
                else:
                    self._totals.bytes_out += final_result.bytes_in
            if self._timestamps:
                timestamps = self._timestamps[top_path]
                timestamps.set(final_result.path)

    def walk_dir(self, dir_path_info: PathInfo) -> None:
        """Recursively optimize a directory."""
        if not self._config.recurse or not dir_path_info.is_dir():
            # Skip
            return

        results = []
        files = []
        dir_path: Path = dir_path_info.path  # type: ignore[reportAssignmentType]

        for name in sorted(dir_path.iterdir()):
            entry_path = dir_path / name
            if entry_path.is_dir():
                path_info = PathInfo(
                    path_info=dir_path_info,
                    path=entry_path,
                )
                self.walk_file(path_info)
            else:
                files.append(entry_path)

        for entry_path in sorted(files):
            path_info = PathInfo(
                path_info=dir_path_info,
                path=entry_path,
            )
            if result := self.walk_file(path_info):
                results.append(result)

        self._finish_results(
            results,
            dir_path_info.top_path,
        )

        if self._timestamps:
            # Compact timestamps after every directory completes
            timestamps = self._timestamps[dir_path_info.top_path]
            timestamps.set(dir_path, compact=True)

    def _walk_container(self, unpack_handler: ContainerHandler):
        """Walk the container."""
        for path_info in unpack_handler.walk():
            container_result = None
            if handler := self._create_handler(path_info):
                container_result = self._handle_file(handler)
            unpack_handler.set_task(path_info, container_result)

    def _handle_container(self, handler: ContainerHandler) -> ApplyResult | None:
        """Optimize a container."""
        result: ApplyResult | None = None
        try:
            # Walk and Unpack or Skip
            self._walk_container(handler)
            if not handler.is_do_repack():
                return result
            # Optimize
            handler.optimize_contents()
            # Repack
            handler = self.create_repack_handler(self._config, handler)
            result = self._pool.apply_async(handler.repack)
        except Exception as exc:
            traceback.print_exc()
            args = (exc,)
            result = self._pool.apply_async(handler.error, args=args)
        return result

    def _handle_file(self, handler):
        """Call the correct walk or pool apply for the handler."""
        if not handler:
            return None
        if isinstance(handler, ContainerHandler):
            # Unpack inline, not in the pool, and walk immediately like dirs.
            result = self._handle_container(handler)
        elif isinstance(handler, ImageHandler):
            result = self._pool.apply_async(handler.optimize_wrapper)
        else:
            msg = f"Bad picopt handler {handler}"
            raise TypeError(msg)
        return result

    def _create_handler(self, path_info: PathInfo):
        handler = self.create_handler(path_info, self._timestamps)
        if handler is None:
            return None

        if self._config.list_only:
            return None

        return handler

    def _walk_file_get_handler(self, path_info: PathInfo) -> Handler | None:
        if path_info.frame is None:
            if self._skipper.is_walk_file_skip(path_info):
                return None

            if path_info.is_dir():
                return self.walk_dir(path_info)

            if self._skipper.is_older_than_timestamp(path_info):
                return None

        return self._create_handler(path_info)

    def walk_file(self, path_info: PathInfo) -> ApplyResult | None:
        """Optimize an individual file."""
        try:
            result = None
            if handler := self._walk_file_get_handler(path_info):
                result = self._handle_file(handler)
            else:
                self._printer.skip_message("")
        except Exception as exc:
            traceback.print_exc()
            apply_kwargs = {
                "path": path_info.path,
                "bytes_in": path_info.bytes_in(),
                "exc": exc,
                "config": self._config,
                "path_info": path_info,
            }
            result = self._pool.apply_async(ReportStats, (), apply_kwargs)
        return result

    def walk(self) -> Totals:
        """Optimize all configured files."""
        self._init_timestamps()

        # Walk each top file
        top_results = {}
        for top_path in self._top_paths:
            dirpath = Treestamps.get_dir(top_path)
            path_info = PathInfo(
                top_path=dirpath, convert=True, path=top_path, is_case_sensitive=None
            )
            result = self.walk_file(path_info)
            if not result:
                continue
            if dirpath not in top_results:
                top_results[dirpath] = []
            top_results[dirpath].append(result)

        # Finish
        for dirpath, results in top_results.items():
            self._finish_results(results, dirpath)

        # Shut down multiprocessing
        self._pool.close()
        self._pool.join()

        cprint("done.")

        if self._timestamps:
            self._timestamps.dumpf()

        self._totals.report(self._printer)
        return self._totals
