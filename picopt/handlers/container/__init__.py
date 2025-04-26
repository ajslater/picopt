"""Container Handler for multiple images like animated images and archives."""

from abc import ABC, abstractmethod
from collections.abc import Generator
from io import BytesIO
from multiprocessing.pool import ApplyResult
from typing import BinaryIO

from termcolor import cprint

from picopt.formats import FileFormat
from picopt.handlers.handler import Handler
from picopt.path import PathInfo
from picopt.stats import ReportStats


class ContainerHandler(Handler, ABC):
    """Container handler for unpacking multiple images and archives."""

    @classmethod
    @abstractmethod
    def identify_format(cls, path_info: PathInfo) -> FileFormat | None:
        """Return the format if this handler can handle this path."""

    @abstractmethod
    def walk(self) -> Generator[PathInfo]:
        """Walk the container."""

    def __init__(self, *args, repack_handler_class: Handler | None = None, **kwargs):
        """Initialize unpack tasks and ."""
        super().__init__(*args, **kwargs)
        self.comment: bytes | None = None
        self._tasks: dict[PathInfo, ApplyResult] = {}
        self._optimized_contents: set[PathInfo] = set()
        self.repack_handler_class = repack_handler_class

    def set_task(self, path_info: PathInfo, mp_result: ApplyResult | None) -> None:
        """Store the mutiprocessing task."""
        if mp_result is None:
            # if not handled by picopt, place it in the results.
            self._optimized_contents.add(path_info)
        else:
            self._tasks[path_info] = mp_result

    def _hydrate_optimized_path_info(self, path_info: PathInfo, report: ReportStats):
        """Replace path_info data."""
        if report.data:
            path_info.set_data(report.data)

    def optimize_contents(self) -> None:
        """Store results from mutiprocessing task."""
        for path_info in tuple(self._tasks):
            mp_results = self._tasks.pop(path_info)
            report = mp_results.get()
            self._hydrate_optimized_path_info(path_info, report)
            self._optimized_contents.add(path_info)

    def get_optimized_contents(self) -> set[PathInfo]:
        """Return optimized contents."""
        return self._optimized_contents

    def optimize(self) -> BinaryIO:
        """NoOp for non packing containers."""
        return BytesIO()


class PackingContainerHandler(ContainerHandler, ABC):
    """Container handler for unpacking and packing multiple images and archives."""

    @abstractmethod
    def pack_into(self) -> BytesIO:
        """Create a container from unpacked contents."""

    def __init__(
        self,
        *args,
        comment: bytes | None = None,
        optimized_contents: set[PathInfo] | None = None,
        **kwargs,
    ):
        """Iinitialize optimized contents."""
        super().__init__(*args, **kwargs)
        if comment:
            self.comment = comment
        if optimized_contents:
            self._optimized_contents = optimized_contents

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
