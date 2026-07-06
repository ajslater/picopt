"""Walk the directory trees and files and call the optimizers."""

from __future__ import annotations

import os
import traceback
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger
from treestamps import Grovestamps, GrovestampsConfig, Treestamps

from picopt import PROGRAM_NAME
from picopt.config import PicoptConfig
from picopt.config.consts import DIR_CONFIG_FILENAME, TIMESTAMPS_CONFIG_KEYS
from picopt.config.dirconfig import DirConfig
from picopt.exceptions import PicoptError
from picopt.log import console
from picopt.log.progress import make_progress
from picopt.log.reporter import Reporter
from picopt.log.summary import Stats
from picopt.log.summary import render as render_summary
from picopt.path import PathInfo, is_path_ignored
from picopt.plugins.base import ContainerHandler, Handler, ImageHandler
from picopt.report import ReportStats
from picopt.walk.handler_factory import HandlerFactory
from picopt.walk.legacy_timestamps import OldTimestamps
from picopt.walk.scheduler import ContainerNode, OptimizeLeafJob, Scheduler
from picopt.walk.skip import WalkSkipper

if TYPE_CHECKING:
    from argparse import Namespace

    from picopt.config.settings import PicoptSettings


class Walk:
    """Methods for walking the tree and handling files."""

    def _create_top_paths(
        self,
    ) -> tuple[Path, ...]:
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

    def __init__(
        self, config: PicoptSettings, arguments: Namespace | None = None
    ) -> None:
        """Initialize."""
        self._config: PicoptSettings = config
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
        # Per-directory .picopt.yaml resolution; args re-layer so CLI wins.
        self._dirconfig: DirConfig = DirConfig(
            PicoptConfig(), arguments, config, self._stats
        )
        self._dir_skippers: dict[Path, WalkSkipper] = {}
        # (st_dev, st_ino) of every walked directory; symlink cycles and
        # duplicate links must not re-optimize the same tree.
        self._visited_dirs: set[tuple[int, int]] = set()

    def _dir_skipper(self, top_path: Path, dir_path: Path) -> WalkSkipper:
        """Return the skipper for a directory's resolved settings. Cached."""
        settings = self._dirconfig.get_settings(top_path, dir_path)
        if settings is self._config:
            return self._skipper
        if (skipper := self._dir_skippers.get(dir_path)) is None:
            skipper = WalkSkipper(settings, self._reporter, self._timestamps)
            self._dir_skippers[dir_path] = skipper
        return skipper

    @staticmethod
    def _config_candidates(root: Path, *, is_dir: bool) -> list[Path]:
        """List candidate ``.picopt.yaml`` files for one target path."""
        # A single-file target only sees its own directory's config.
        if not is_dir:
            return [root.parent / DIR_CONFIG_FILENAME]
        try:
            return sorted(root.rglob(DIR_CONFIG_FILENAME))
        except OSError:
            return []

    @staticmethod
    def _config_chunk(root: Path, config_file: Path, *, is_dir: bool) -> bytes | None:
        """Return one config file's fingerprint contribution, or None."""
        try:
            data = config_file.read_bytes()
        except OSError:
            # Covers missing files and directories named like the config.
            return None
        # A path relative to the target keeps the digest stable across
        # cwd/mount changes; add/remove/rename still flips it.
        rel = config_file.relative_to(root) if is_dir else config_file.name
        return str(rel).encode() + b"\0" + data + b"\0"

    def _dir_config_fingerprint(self) -> str:
        """
        Hash every ``.picopt.yaml`` under the target paths.

        Folded into the treestamps ``program_config`` so that editing,
        adding, or removing any directory config flips the digest and the
        affected tree re-processes on the next run — over-invalidation
        that is always safe (re-checking an already-optimized file is a
        cheap skip) and never wrong-skips a file whose effective config
        changed.
        """
        hasher = sha256()
        seen: set[Path] = set()
        for path in self._config.paths:
            root = Path(path)
            is_dir = root.is_dir()
            for config_file in self._config_candidates(root, is_dir=is_dir):
                if config_file in seen:
                    continue
                seen.add(config_file)
                chunk = self._config_chunk(root, config_file, is_dir=is_dir)
                if chunk is not None:
                    hasher.update(chunk)
        return hasher.hexdigest()

    def _init_timestamps(self) -> None:
        """Init timestamps."""
        if not self._config.timestamps:
            return
        # Treestamps filters program_config by program_config_keys; build a
        # shallow Mapping with only those keys so we don't have to serialize
        # the whole frozen dataclass (especially the computed sub-fields,
        # which carry re.Pattern objects and class-keyed dicts).
        program_config: dict[str, Any] = {
            key: getattr(self._config, key) for key in TIMESTAMPS_CONFIG_KEYS
        }
        # Fold a fingerprint of the directory configs into the program
        # config so any change to a .picopt.yaml invalidates its tree's
        # timestamps (the single global program_config can't otherwise see
        # per-directory config changes).
        program_config["_dir_config_fingerprint"] = self._dir_config_fingerprint()
        config = GrovestampsConfig(
            paths=self._top_paths,
            program_name=PROGRAM_NAME,
            verbose=self._config.verbose,
            symlinks=self._config.symlinks,
            ignore=self._config.ignore,
            check_config=self._config.timestamps_check_config,
            program_config=program_config,
            program_config_keys=TIMESTAMPS_CONFIG_KEYS | {"_dir_config_fingerprint"},
        )
        self._timestamps = Grovestamps(config)
        for timestamps in self._timestamps.values():
            OldTimestamps(self._config, timestamps).import_old_timestamps()
        self._skipper.set_timestamps(self._timestamps)
        if tps := tuple(tp for tp in self._top_paths if tp in self._timestamps):
            roots = ", ".join(sorted(str(p) for p in tps))
            logger.info(f"Loaded timestamps for: {roots}")

    def _dump_timestamps(self) -> None:
        """Dump timestamps to disk, with a log line per top path."""
        if not self._timestamps:
            return
        if dumped := self._timestamps.dumpf():
            roots = ", ".join(str(p) for p in dumped)
            logger.info(f"Dumped timestamps for: {roots}")

    def _enqueue_children(
        self, sched: Scheduler, node: ContainerNode, children: list[PathInfo]
    ) -> None:
        """Bridge between scheduler and HandlerFactory for container children."""
        for path_info in children:
            try:
                # Members inherit their container's (per-directory) config;
                # nested containers pass it down automatically.
                handler = self._create_handler(path_info, node.handler.config)
            except Exception as exc:
                # A member that can't even be sniffed (e.g. a decompression
                # bomb) is one error, not a run-ender. Pass it through
                # unmodified so the repacked archive keeps it.
                traceback.print_exc()
                report = ReportStats(
                    path=Path(path_info.full_output_name()),
                    bytes_in=path_info.bytes_in(),
                    exc=exc,
                    config=self._config,
                    path_info=path_info,
                )
                self._reporter.record_report(report)
                node.handler.get_optimized_contents().add(path_info)
                continue
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
        if not dir_path_info.is_dir():
            return

        dir_path = dir_path_info.path
        if not dir_path:
            return

        # The directory's own .picopt.yaml governs recursion into it.
        settings = self._dirconfig.get_settings(dir_path_info.top_path, dir_path)
        if not settings.recurse:
            return

        try:
            dir_stat = dir_path.stat()
        except OSError:
            return
        dir_key = (dir_stat.st_dev, dir_stat.st_ino)
        if dir_key in self._visited_dirs:
            logger.debug(f"Skip: directory already visited (symlink loop): {dir_path}")
            return
        self._visited_dirs.add(dir_key)

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

    def _create_handler(
        self, path_info: PathInfo, settings: PicoptSettings | None = None
    ) -> Handler | None:
        handler = self._handler_factory.create_handler(
            path_info, self._timestamps, settings=settings
        )
        if handler is None:
            return None

        if self._config.list_only:
            return None

        return handler

    def _walk_file_get_handler(
        self, path_info: PathInfo, scheduler: Scheduler
    ) -> Handler | None:
        settings: PicoptSettings | None = None
        if path_info.frame is None:
            skipper = self._skipper
            if path_info.path is not None:
                dir_path = Treestamps.get_dir(path_info.path)
                skipper = self._dir_skipper(path_info.top_path, dir_path)
                settings = self._dirconfig.get_settings(path_info.top_path, dir_path)

            if skipper.is_walk_file_skip(path_info):
                return None

            if path_info.is_dir():
                self.walk_dir(path_info, scheduler)
                return None

            if skipper.is_older_than_timestamp(path_info):
                return None

        handler = self._create_handler(path_info, settings)
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

    @staticmethod
    def _count_stops_here(
        settings: PicoptSettings,
        path: Path,
        name: str,
        *,
        is_symlink: bool,
        is_dir: bool,
    ) -> bool:
        """Whether the walk would not recurse into ``path`` (mirror walk_file)."""
        return bool(
            not settings.recurse
            or (not settings.symlinks and is_symlink)
            or name in WalkSkipper.SKIP_FILENAMES
            or not is_dir
            or is_path_ignored(settings, path, ignore_case=False)
        )

    def _count(
        self,
        top_path: Path,
        path: Path,
        name: str,
        visited: set[tuple[int, int]],
        *,
        is_symlink: bool,
        is_dir: bool,
    ) -> int:
        """
        Count progress-bar advances for ``path``.

        Pre-resolved ``is_symlink`` / ``is_dir`` come from ``os.scandir`` on
        recursive calls so deep trees don't pay an extra ``stat`` per entry.
        """
        # Mirror the walk's per-directory settings (cached in DirConfig).
        settings = self._dirconfig.get_settings(
            top_path, path if is_dir else path.parent
        )
        if self._count_stops_here(
            settings, path, name, is_symlink=is_symlink, is_dir=is_dir
        ):
            return 1
        try:
            # Mirror walk_dir's symlink-loop guard or a cycle never ends.
            dir_stat = path.stat()
            dir_key = (dir_stat.st_dev, dir_stat.st_ino)
            if dir_key in visited:
                return 0
            visited.add(dir_key)
            with os.scandir(path) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError:
            return 1
        total = 0
        for entry in entries:
            try:
                total += self._count(
                    top_path,
                    Path(entry.path),
                    entry.name,
                    visited,
                    is_symlink=entry.is_symlink(),
                    is_dir=entry.is_dir(),
                )
            except OSError:
                total += 1
        return total

    def _count_path(self, path: Path) -> int:
        """
        Mirror walk_file's recursion gate to count progress-bar advances.

        Each non-recursing visit produces one progress mark — top-level
        files, ignored/symlink/timestamp-file dirs, and so on. Recursed
        directories contribute their children's counts instead. In-archive
        children don't emit marks (workers can't reach the live region),
        so they're not counted.
        """
        try:
            return self._count(
                Treestamps.get_dir(path),
                path,
                path.name,
                set(),
                is_symlink=path.is_symlink(),
                is_dir=path.is_dir(),
            )
        except OSError:
            return 1

    def _count_total(self) -> int:
        """Total advance count for the progress bar across all top paths."""
        return sum(self._count_path(top) for top in self._top_paths)

    def walk(self) -> Stats:
        """Optimize all configured files."""
        self._init_timestamps()
        self._visited_dirs.clear()

        max_workers = self._config.jobs or os.cpu_count() or 1
        # The pre-count re-walks the whole tree; don't pay for it when the
        # progress bar isn't shown at all.
        progress_enabled = self._config.verbose > 0
        total = self._count_total() if progress_enabled else 0
        progress = make_progress(console, enabled=progress_enabled, total=total)
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

        self._dump_timestamps()

        if self._config.verbose > 0:
            render_summary(self._stats, console, dry_run=bool(self._config.dry_run))
        return self._stats
