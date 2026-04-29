"""Walk the directory trees and files and call the optimizers."""

from __future__ import annotations

import os
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from treestamps import Grovestamps, GrovestampsConfig, Treestamps

from picopt import PROGRAM_NAME
from picopt.config.consts import TIMESTAMPS_CONFIG_KEYS
from picopt.exceptions import PicoptError
from picopt.log import console
from picopt.log.progress import make_progress
from picopt.log.reporter import Reporter
from picopt.log.summary import Stats
from picopt.log.summary import render as render_summary
from picopt.path import PathInfo
from picopt.plugins.base import ContainerHandler, Handler, ImageHandler
from picopt.report import ReportStats
from picopt.walk.handler_factory import HandlerFactory
from picopt.walk.legacy_timestamps import OldTimestamps
from picopt.walk.scheduler import ContainerNode, OptimizeLeafJob, Scheduler
from picopt.walk.skip import WalkSkipper

if TYPE_CHECKING:
    from confuse.templates import AttrDict


class Walk:
    """Methods for walking the tree and handling files."""

    def _create_top_paths(
        self,
    ) -> tuple[Path, Path] | tuple[Path]:
        """Create and Validate that top paths exist."""
        top_paths = []
        paths: tuple[Path, ...] = tuple(sorted(frozenset(self._config.paths)))
        for path in paths:
            if not path.exists():
                msg = f"Path does not exist: {path}"
                raise PicoptError(msg)
            if path.is_symlink() and not self._config.symlinks:
                continue
            top_paths.append(path)
        if not top_paths:
            msg = "No paths to optimize."
            raise PicoptError(msg)
        return tuple(top_paths)

    def __init__(self, config: AttrDict) -> None:
        """Initialize."""
        self._config: AttrDict = config
        self._top_paths: tuple[Path, ...] = self._create_top_paths()
        self._stats: Stats = Stats(
            timestamps_active=bool(config.timestamps or config.after),
            dry_run_active=bool(config.dry_run),
        )
        # Progress is built later (in walk()) once we know we're really running.
        self._reporter: Reporter = Reporter(
            stats=self._stats, verbose=int(config.verbose)
        )
        self._executor: ProcessPoolExecutor = ProcessPoolExecutor(
            max_workers=self._config.jobs or None
        )
        self._timestamps: Grovestamps | None = None  # reassigned at start of run
        self._skipper: WalkSkipper = WalkSkipper(config, self._reporter)
        self._handler_factory: HandlerFactory = HandlerFactory(config, self._reporter)

    def _init_timestamps(self) -> None:
        """Init timestamps."""
        if not self._config.timestamps:
            return
        # ``verbose=0`` keeps treestamps's own internal printer silent so it
        # doesn't bypass the Rich Live region with its own dot output.
        config = GrovestampsConfig(
            paths=self._top_paths,
            program_name=PROGRAM_NAME,
            verbose=0,
            symlinks=self._config.symlinks,
            ignore=self._config.ignore,
            check_config=self._config.timestamps_check_config,
            program_config=self._config,
            program_config_keys=TIMESTAMPS_CONFIG_KEYS,
        )
        self._timestamps = Grovestamps(config)
        for timestamps in self._timestamps.values():
            OldTimestamps(self._config, timestamps).import_old_timestamps()
        self._skipper.set_timestamps(self._timestamps)

    def _enqueue_children(
        self, sched: Scheduler, node: ContainerNode, children: list[PathInfo]
    ) -> None:
        """Bridge between scheduler and HandlerFactory for container children."""
        for path_info in children:
            handler = self._create_handler(path_info)
            if handler is None:
                # noop copy — child passes through unmodified
                node.handler.get_optimized_contents().add(path_info)
                continue
            if isinstance(handler, ContainerHandler):
                sched.enqueue_container(handler, parent=node)
            elif isinstance(handler, ImageHandler):
                sched.enqueue_leaf(
                    OptimizeLeafJob(handler=handler, path_info=path_info),
                    parent=node,
                )

    def walk_dir(self, dir_path_info: PathInfo, scheduler: Scheduler) -> None:
        """Recursively walk a directory, enqueuing jobs into the scheduler."""
        if not self._config.recurse or not dir_path_info.is_dir():
            return

        dir_path = dir_path_info.path
        if not dir_path:
            return

        scheduler.begin_dir(dir_path_info.top_path, dir_path)
        try:
            files = []
            for name in sorted(dir_path.iterdir()):
                entry_path = dir_path / name
                if entry_path.is_dir():
                    path_info = PathInfo(
                        path_info=dir_path_info,
                        path=entry_path,
                    )
                    self.walk_file(path_info, scheduler)
                else:
                    files.append(entry_path)

            for entry_path in sorted(files):
                path_info = PathInfo(
                    path_info=dir_path_info,
                    path=entry_path,
                )
                self.walk_file(path_info, scheduler)
        except Exception:
            scheduler.cancel_dir(dir_path)
            raise
        scheduler.seal_dir(dir_path)

    def _handle_file(
        self, handler: Handler, path_info: PathInfo, scheduler: Scheduler
    ) -> None:
        """Enqueue the correct job for the handler type."""
        match handler:
            case ContainerHandler():
                scheduler.enqueue_container(handler)
            case ImageHandler():
                scheduler.enqueue_leaf(
                    OptimizeLeafJob(handler=handler, path_info=path_info),
                )
            case _:
                msg = f"Bad picopt handler {handler}"
                raise TypeError(msg)

    def _create_handler(self, path_info: PathInfo) -> Handler | None:
        handler = self._handler_factory.create_handler(path_info, self._timestamps)
        if handler is None:
            return None

        if self._config.list_only:
            return None

        return handler

    def _walk_file_get_handler(
        self, path_info: PathInfo, scheduler: Scheduler
    ) -> Handler | None:
        if path_info.frame is None:
            if self._skipper.is_walk_file_skip(path_info):
                return None

            if path_info.is_dir():
                self.walk_dir(path_info, scheduler)
                return None

            if self._skipper.is_older_than_timestamp(path_info):
                return None

        handler = self._create_handler(path_info)
        if not handler:
            logger.debug(f"Skip: no handler: {path_info.full_output_name()}")
            self._stats.record_skipped()
            self._reporter.progress.mark_skipped()
        return handler

    def walk_file(self, path_info: PathInfo, scheduler: Scheduler) -> None:
        """Optimize an individual file by enqueuing into the scheduler."""
        try:
            if handler := self._walk_file_get_handler(path_info, scheduler):
                self._handle_file(handler, path_info, scheduler)
        except Exception as exc:
            traceback.print_exc()
            report = ReportStats(
                path=path_info.path or Path(),
                bytes_in=path_info.bytes_in(),
                exc=exc,
                config=self._config,
                path_info=path_info,
            )
            scheduler.accept_prebuilt_report(report, path_info.top_path)

    def _walk_top_path(self, top_path: Path, scheduler: Scheduler) -> None:
        dirpath = Treestamps.get_dir(top_path)
        path_info = PathInfo(
            top_path=dirpath, convert=True, path=top_path, is_case_sensitive=None
        )
        self.walk_file(path_info, scheduler)

    def walk(self) -> Stats:
        """Optimize all configured files."""
        self._init_timestamps()

        max_workers = self._config.jobs or os.cpu_count() or 1
        progress = make_progress(console, enabled=self._config.verbose > 0)
        # Replace the no-op progress that the skipper / factory captured at
        # construction time so they advance the real bar.
        self._reporter.progress = progress

        scheduler = Scheduler(
            config=self._config,
            executor=self._executor,
            timestamps=self._timestamps,
            reporter=self._reporter,
            max_workers=max_workers,
            create_repack_handler=HandlerFactory.create_repack_handler,
            child_enqueue_callback=self._enqueue_children,
        )

        with progress:
            for top_path in self._top_paths:
                self._walk_top_path(top_path, scheduler)

            scheduler.run()

            self._executor.shutdown(wait=True)

        if self._timestamps:
            self._timestamps.dumpf()

        if self._config.verbose > 0:
            render_summary(self._stats, console, dry_run=bool(self._config.dry_run))
        return self._stats
