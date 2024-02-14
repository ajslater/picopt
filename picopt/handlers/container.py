"""Optimize comic archives."""
from abc import ABCMeta, abstractmethod
from collections.abc import Generator, Mapping
from io import BytesIO
from multiprocessing.pool import ApplyResult
from typing import BinaryIO

from confuse.templates import AttrDict
from termcolor import cprint

from picopt.formats import FileFormat
from picopt.handlers.handler import Handler
from picopt.path import PathInfo
from picopt.stats import ReportStats


class ContainerHandler(Handler, metaclass=ABCMeta):
    """Comic format class."""

    CONTAINER_DIR_SUFFIX: str = ".dir"
    CONVERT: bool = True

    @classmethod
    @abstractmethod
    def identify_format(cls, path_info: PathInfo) -> FileFormat | None:
        """Return the format if this handler can handle this path."""

    @abstractmethod
    def unpack_into(self) -> Generator[PathInfo, None, None]:
        """Unpack a container into a tmp dir to work on it's contents."""

    @abstractmethod
    def pack_into(self) -> BytesIO:
        """Create a container from a tmp dir's contents."""

    def __init__(
        self,
        config: AttrDict,
        path_info: PathInfo,
        file_format: FileFormat,
        info: Mapping,
    ):
        """Unpack a container with a subclass's unpacker."""
        super().__init__(
            config,
            path_info,
            file_format,
            info,
        )
        self.comment: bytes | None = None
        self._tasks: dict[PathInfo, ApplyResult] = {}
        self._optimized_contents: dict[PathInfo, bytes] = {}

    def get_container_paths(self) -> tuple[str, ...]:
        """Create a container path for output."""
        return (*self.path_info.container_paths, str(self.original_path))

    def unpack(self) -> Generator[PathInfo, None, None]:
        """Create directory and unpack container."""
        if self.config.verbose:
            cprint(f"Unpacking {self.original_path}...", end="")

        yield from self.unpack_into()

        if self.config.verbose:
            cprint("done")

    def set_task(self, path_info: PathInfo, mp_result: ApplyResult | None) -> None:
        """Store the mutiprocessing task."""
        if mp_result is None:
            # if not handled by picopt, place it in the results.
            self._optimized_contents[path_info] = path_info.data()
        else:
            self._tasks[path_info] = mp_result

    def optimize_contents(self) -> None:
        """Store results from mutiprocessing task."""
        for path_info in tuple(self._tasks):
            mp_results = self._tasks.pop(path_info)
            report = mp_results.get()
            # Clearing has to happen AFTER mp_results.get() or we risk not passing the data
            path_info.data_clear()
            self._optimized_contents[path_info] = report.data

    def optimize(self) -> BinaryIO:
        """Run pack_into."""
        return self.pack_into()

    def repack(self) -> ReportStats:
        """Create a new container and clean up the tmp dir."""
        if self.config.verbose:
            cprint(f"Repacking {self.final_path}...", end="")

        report_stats = self.optimize_wrapper()
        if self.config.verbose:
            cprint("done")
        return report_stats
