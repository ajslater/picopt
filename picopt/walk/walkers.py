"""Methods for walking the tree and handling files."""

import traceback
from multiprocessing.pool import ApplyResult
from pathlib import Path

from picopt.handlers.container import ContainerHandler
from picopt.handlers.factory import (
    create_handler,
    create_repack_handler,
    get_repack_handler_class,
)
from picopt.handlers.image import ImageHandler
from picopt.path import PathInfo
from picopt.stats import ReportStats
from picopt.walk.skippers import WalkSkippers


class WalkWalkers(WalkSkippers):
    """Methods for walking the tree and handling files."""

    def _finish_results(
        self,
        results: list[ApplyResult],
        top_path: Path,
        in_container: bool,
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
            if self._config.timestamps and not in_container:
                timestamps = self._timestamps[top_path]
                timestamps.set(final_result.path)

    def walk_dir(self, path_info: PathInfo) -> None:
        """Recursively optimize a directory."""
        if not self._config.recurse or path_info.in_container or not path_info.is_dir():
            # Skip
            return

        results = []
        files = []
        dir_path: Path = path_info.path  # type: ignore[reportAssignmentType]

        for name in sorted(dir_path.iterdir()):
            entry_path = dir_path / name
            if entry_path.is_dir():
                path_info = PathInfo(
                    path_info.top_path,
                    path_info.convert,
                    path=entry_path,
                    in_container=path_info.in_container,
                    is_case_sensitive=path_info.is_case_sensitive,
                )
                self.walk_file(path_info)
            else:
                files.append(entry_path)

        for entry_path in sorted(files):
            path_info = PathInfo(
                path_info.top_path,
                path_info.convert,
                path=entry_path,
                in_container=path_info.in_container,
                is_case_sensitive=path_info.is_case_sensitive,
            )
            if result := self.walk_file(path_info):
                results.append(result)

        self._finish_results(
            results,
            path_info.top_path,
            path_info.in_container,
        )

        if self._config.timestamps:
            # Compact timestamps after every directory completes
            timestamps = self._timestamps[path_info.top_path]
            timestamps.set(dir_path, compact=True)

    def _walk_container(self, unpack_handler: ContainerHandler) -> ApplyResult | None:
        """Optimize a container."""
        result: ApplyResult | None
        try:
            repack_handler_class = get_repack_handler_class(
                self._config, unpack_handler
            )
            if not repack_handler_class:
                return self._skip_no_repack_handler(unpack_handler)
            for path_info in unpack_handler.unpack():
                container_result = self.walk_file(path_info)
                unpack_handler.set_task(path_info, container_result)
            unpack_handler.optimize_contents()
            repack_handler = create_repack_handler(
                self._config, unpack_handler, repack_handler_class
            )
            if not repack_handler:
                return self._skip_no_repack_handler(unpack_handler)
            try:
                # at this point handler_final_result array contains buffers not mp-results
                result = self._pool.apply_async(repack_handler.repack)
            except Exception as exc:
                traceback.print_exc()
                args = (exc,)
                result = self._pool.apply_async(repack_handler.error, args=args)
        except Exception as exc:
            traceback.print_exc()
            args = (exc,)
            result = self._pool.apply_async(unpack_handler.error, args=args)
        return result

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
            apply_kwargs = {
                "path": path_info.path,
                "bytes_in": path_info.bytes_in(),
                "exc": exc,
                "config": self._config,
                "path_info": path_info,
            }
            result = self._pool.apply_async(ReportStats, (), apply_kwargs)
        return result
