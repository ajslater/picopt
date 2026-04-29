"""
Container handler base.

The old hierarchy was::

    ContainerHandler (ABC)
        PackingContainerHandlerMixin (ABC)
        PackingContainerHandler (ABC)
            PackingArchiveHandler (ABC)
        ArchiveHandler (ABC)

with the packing-or-not distinction enforced by which mixin a class
multiply-inherited. That mechanism produced ``# pyright: ignore`` comments
all over the place because the type system couldn't see the attributes the
mixin was supposed to provide.

The new shape: every container is one class. ``CAN_PACK`` is a class flag
that says whether ``pack_into`` and ``repack`` are real implementations or
``NotImplementedError``. Read-only containers (RAR) set ``CAN_PACK = False``
and the routing layer requires them to have a ``convert`` target.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import copy
from typing import TYPE_CHECKING, Any, BinaryIO

from loguru import logger
from typing_extensions import override

from picopt.log.reporter import Reporter
from picopt.plugins.base.handler import Handler

if TYPE_CHECKING:
    from collections.abc import Generator

    from confuse import AttrDict
    from treestamps import Grovestamps

    from picopt.path import PathInfo
    from picopt.report import ReportStats
    from picopt.walk.skip import WalkSkipper


class ContainerHandler(Handler, ABC):
    """Container of multiple files (animated images and archives)."""

    CONTAINER_TYPE: str = "Container"
    CAN_PACK: bool = True

    def __init__(
        self,
        *args: Any,
        timestamps: Grovestamps | None = None,
        repack_handler_class: type[ContainerHandler] | None = None,
        comment: bytes | None = None,
        optimized_contents: set[PathInfo] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize instance vars."""
        super().__init__(*args, **kwargs)
        # Config gets mutated for pickling protection during repack.
        self.config: AttrDict = copy(self.config)
        self._timestamps: Grovestamps | None = timestamps
        self.repack_handler_class: type[ContainerHandler] | None = repack_handler_class
        # Lazy import to avoid a cycle (walk.skip imports nothing of ours).
        from picopt.walk.skip import WalkSkipper

        # Workers don't share Reporter with the parent process; give each
        # worker a detached one so skip-side counters/marks become no-ops.
        self._skipper: WalkSkipper | None = WalkSkipper(
            self.config, Reporter(), timestamps, in_archive=True
        )
        self.comment: bytes | None = comment
        self._optimized_contents: set[PathInfo] = optimized_contents or set()
        self._do_repack: bool = bool(optimized_contents)

    # ----------------------------------------------------------- walk/unpack

    @abstractmethod
    def walk(self) -> Generator[PathInfo]:
        """Yield each child PathInfo in the container."""

    def _walk_finish(self) -> None:
        if self.config.verbose < 2:  # noqa: PLR2004
            return
        if self._do_repack and self._skipper:
            logger.info(f"Optimizing contents in {self.path_info.full_output_name()}")
        else:
            logger.info(
                f"Skip: {self.CONTAINER_TYPE}, contents skipped. "
                f"Optimizing during repack: {self.path_info.full_output_name()}"
            )

    # ----------------------------------------------------- task accumulation

    def is_do_repack(self) -> bool:
        """Whether any contained file changed and the container needs repacking."""
        return self._do_repack

    def set_do_repack(self, *, do_repack: bool) -> None:
        """Set the flag determining whether the container needs repack."""
        self._do_repack = do_repack

    def hydrate_optimized_path_info(
        self,
        path_info: PathInfo,
        report: ReportStats,
    ) -> None:
        """
        Pull optimized bytes from a completed report back onto path_info.

        Subclasses (archive, PDF) override to handle renames.
        Called by the scheduler after each leaf completes.
        """
        if report.data:
            path_info.set_data(report.data)

    def get_optimized_contents(
        self,
    ) -> set[PathInfo]:
        """Return optimized contents."""
        return self._optimized_contents

    # ------------------------------------------------------------- packing

    def pack_into(self) -> BinaryIO:
        """
        Build the new packed buffer from optimized contents.

        Read-only containers (CAN_PACK = False) leave this raising; routing
        forces them through a different convert handler.
        """
        msg = f"{type(self).__name__} cannot pack (read-only container)."
        raise NotImplementedError(msg)

    @override
    def optimize(self) -> BinaryIO:
        """Repack: produce the final container buffer."""
        if not self.CAN_PACK:
            msg = f"{type(self).__name__} cannot optimize a non-packing container."
            raise NotImplementedError(msg)
        if self.config.verbose > 1:
            logger.info(f"Repacking {self.path_info.full_output_name()}…")
        return self.pack_into()

    def __getstate__(self) -> dict[str, Any]:
        """Drop Grovestamps for worker handoff; its ruamel.yaml Reader owns an un-picklable BufferedReader."""
        state = self.__dict__.copy()
        state["_timestamps"] = None
        state["_skipper"] = None
        return state

    def repack(self) -> ReportStats:
        """Public alias used by the multiprocessing pool dispatcher."""
        return self.optimize_wrapper()
