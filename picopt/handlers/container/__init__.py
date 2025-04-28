"""Container Handler for multiple images like animated images and archives."""

from abc import ABC, abstractmethod
from collections.abc import Generator
from io import BytesIO
from multiprocessing.pool import ApplyResult
from typing import BinaryIO

from treestamps import Grovestamps

from picopt.formats import FileFormat
from picopt.handlers.handler import Handler
from picopt.path import PathInfo
from picopt.report import ReportStats
from picopt.walk.skip import WalkSkipper


class ContainerHandler(Handler, ABC):
    """Container handler for unpacking multiple images and archives."""

    CONTAINER_TYPE = "Container"

    @classmethod
    @abstractmethod
    def identify_format(cls, path_info: PathInfo) -> FileFormat | None:
        """Return the format if this handler can handle this path."""

    def _walk_finish(self) -> None:
        if not self.config.verbose:
            return
        self._messenger.done()
        if self._do_repack and self._skipper:
            self._messenger.optimize_container(str(self.path_info.path))
        else:
            self._messenger.skip_container(
                self.CONTAINER_TYPE, str(self.path_info.path)
            )

    @abstractmethod
    def walk(self) -> Generator[PathInfo]:
        """Walk the container."""

    def __init__(
        self,
        *args,
        timestamps: Grovestamps | None = None,
        repack_handler_class: Handler | None = None,
        **kwargs,
    ):
        """Initialize unpack tasks and ."""
        super().__init__(*args, **kwargs)
        self._timestamps = timestamps
        self.repack_handler_class = repack_handler_class
        self._skipper = WalkSkipper(self.config, timestamps, in_archive=True)
        self.comment: bytes | None = None
        self._tasks: dict[PathInfo, ApplyResult] = {}
        self._optimized_contents: set[PathInfo] = set()
        self._do_repack = False

    def is_do_repack(self):
        """Return if any changes were made and we should repack."""
        return self._do_repack

    def set_task(self, path_info: PathInfo, mp_result: ApplyResult | None) -> None:
        """Store the mutiprocessing task."""
        if mp_result is None:
            # if not handled by picopt, place it in the results.
            self._optimized_contents.add(path_info)
            self._messenger.copied_message()
        else:
            self._tasks[path_info] = mp_result
            self._do_repack = True
            self._messenger.handled_message()

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
        self._timestamps = None
        self._skipper = None

    def get_optimized_contents(self) -> set[PathInfo]:
        """Return optimized contents."""
        return self._optimized_contents

    def optimize(self) -> BinaryIO:
        """NoOp for non packing containers."""
        reason = "Non packing container doesn't optimize."
        raise NotImplementedError(reason)


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
        """Copy optimized contents from previous handler."""
        super().__init__(*args, **kwargs)
        if comment:
            self.comment = comment
        if optimized_contents:
            self._optimized_contents = optimized_contents

    def optimize(self) -> BinaryIO:
        """Run pack_into."""
        self._messenger.container_repacking(self.path_info.full_output_name())
        buffer = self.pack_into()
        self._messenger.done()
        return buffer

    def repack(self) -> ReportStats:
        """Create a new container and clean up the tmp dir."""
        return self.optimize_wrapper()
