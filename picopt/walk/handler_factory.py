"""
Return a handler for a path.

Reads the routing table from :mod:`picopt.plugins` (the registry) and the
per-handler probed pipeline from ``config.computed.handler_stages`` (populated
by :mod:`picopt.config.handlers` at startup).

Handler-class selection rules for an input :class:`FileFormat` ``ff``:

1. If the user asked for conversion (and either the format is not an archive
   or the caller is asking for a *repack* handler), pick the first handler in
   ``routes_by_format()[ff].convert`` whose pipeline was probed available at
   config time and whose ``OUTPUT_FORMAT_STR`` is in the user's
   ``--convert-to`` set. The pipeline-availability filter is what makes the
   WebP convert chain ``(Img2WebP, WebPMux, PILPack)`` actually fall through
   to ``PILPack`` when the external tools are missing.

2. Otherwise, fall back to the native handler for that FileFormat, again only
   if its pipeline is available.

3. For repack callers, the chosen handler must additionally have ``CAN_PACK``
   set, replacing the old ``isinstance(handler_cls, PackingContainerHandler |
   PackingArchiveHandler)`` check.
"""

from __future__ import annotations

from traceback import print_exc
from typing import TYPE_CHECKING, Any

from loguru import logger

from picopt import plugins as registry
from picopt.plugins.base import (
    ArchiveHandler,
    ContainerHandler,
    Handler,
    ImageHandler,
)
from picopt.walk.detect_format import detect_format

if TYPE_CHECKING:
    from collections.abc import Mapping

    from treestamps import Grovestamps

    from picopt.config.settings import PicoptSettings
    from picopt.log.reporter import Reporter
    from picopt.path import PathInfo
    from picopt.plugins.base.format import FileFormat


class HandlerFactory:
    """Handler factory for creating format-appropriate handlers."""

    def __init__(self, config: PicoptSettings, reporter: Reporter) -> None:
        """Initialize with config and reporter."""
        self._config: PicoptSettings = config
        self._reporter: Reporter = reporter

    def _lookup_route(
        self,
        file_format: FileFormat | None,
    ) -> tuple | None:
        if not file_format:
            return None
        if file_format.format_str not in self._config.formats:
            return None

        routes = registry.routes_by_format()
        entry = routes.get(file_format)
        if entry is None:
            return None
        return entry

    def _is_pipeline_available(self, handler_cls: type[Handler]) -> bool:
        """
        Whether the config-time probe found a workable pipeline for this handler.

        A handler is "available" iff every tier in its ``PIPELINE`` produced a
        selected tool. Handlers with an empty PIPELINE (e.g. archive handlers
        that pack via Python libraries, or PILPack sentinels) are always
        available — there is nothing to be missing.
        """
        if not handler_cls.PIPELINE:
            return True
        stages = self._config.computed.handler_stages.get(handler_cls)
        if stages is None:
            return False
        return len(stages) == len(handler_cls.PIPELINE)

    def _pick_handler_class_choose_converter(
        self, candidate: type[Handler], convert_to: frozenset[str]
    ) -> type[Handler] | None:
        if candidate.OUTPUT_FORMAT_STR not in convert_to:
            return None
        if not self._is_pipeline_available(candidate):
            return None
        return candidate

    def _pick_handler_class_converter(
        self,
        file_format: FileFormat | None,
        convert_chain: tuple[type[Handler], ...],
        *,
        convert: bool,
        repack: bool,
    ) -> type[Handler] | None:
        # Conversion path: archives only convert during the repack pass; for
        # images we prefer the convert handler at first sight because it's
        # often faster than translating through PIL.
        if not file_format:
            return None
        handler_cls: type[Handler] | None = None
        convert_to: frozenset[str] = frozenset(self._config.convert_to or ())
        if convert and (not file_format.archive or repack):
            for candidate in convert_chain:
                if handler_cls := self._pick_handler_class_choose_converter(
                    candidate, convert_to
                ):
                    break
        return handler_cls

    def _pick_handler_class(
        self,
        file_format: FileFormat | None,
        *,
        convert: bool,
        repack: bool = False,
    ) -> type[Handler] | None:
        """Return a handler class for the file format."""
        entry = self._lookup_route(file_format)
        if not entry:
            return None
        native, convert_chain = entry

        handler_cls = self._pick_handler_class_converter(
            file_format, convert_chain, convert=convert, repack=repack
        )

        # Native fallback.
        if (
            handler_cls is None
            and native is not None
            and self._is_pipeline_available(native)
        ):
            handler_cls = native

        # Repack callers need a packing-capable handler.
        if (
            repack
            and handler_cls is not None
            and not (issubclass(handler_cls, ContainerHandler) and handler_cls.CAN_PACK)
        ):
            handler_cls = None

        return handler_cls

    def _get_repack_handler_class(
        self,
        path_info: PathInfo,
        file_format: FileFormat,
    ) -> type[ContainerHandler] | None:
        """Get the repack handler class or None if not configured."""
        repack_handler_class: type[ContainerHandler] | None = None
        try:
            picked = self._pick_handler_class(
                file_format,
                convert=path_info.convert,
                repack=True,
            )
            if picked is not None and issubclass(picked, ContainerHandler):
                repack_handler_class = picked
        except OSError as exc:
            msg = (
                f"getting repack container handler for "
                f"{path_info.full_output_name()}: {exc}"
            )
            logger.warning(msg)
            print_exc()

        if (
            not repack_handler_class
            and self._config.verbose > 1
            and not self._config.list_only
        ):
            fmt = str(file_format) if file_format else "unknown"
            msg = (
                f"Skip: ({fmt}) is not an enabled image or container format: "
                f"{path_info.full_output_name()}"
            )
            logger.debug(msg)

        return repack_handler_class

    def _create_handler_get_class_and_format(
        self, path_info: PathInfo
    ) -> tuple[FileFormat | None, type[Handler] | None, Mapping[str, Any]]:
        handler_cls: type[Handler] | None = None
        try:
            file_format, info = detect_format(
                path_info, keep_metadata=self._config.keep_metadata
            )
            handler_cls = self._pick_handler_class(
                file_format,
                convert=path_info.convert,
            )
        except OSError as exc:
            logger.warning(f"getting handler for {path_info.full_output_name()}: {exc}")
            print_exc()
            file_format = None
            info = {}
        return file_format, handler_cls, info

    def create_handler(
        self,
        path_info: PathInfo,
        timestamps: Grovestamps | None = None,
    ) -> Handler | None:
        """Return a handler for the image format."""
        if path_info.noop:
            return None

        file_format, handler_cls, info = self._create_handler_get_class_and_format(
            path_info
        )

        if not handler_cls or not file_format:
            return None

        kwargs: dict[str, Any] = {}
        if issubclass(handler_cls, ImageHandler):
            kwargs["info"] = info
        if issubclass(handler_cls, ContainerHandler):
            repack_handler_class = self._get_repack_handler_class(
                path_info, file_format
            )
            if repack_handler_class:
                kwargs["repack_handler_class"] = repack_handler_class
                if issubclass(handler_cls, ArchiveHandler):
                    kwargs["timestamps"] = timestamps
            else:
                return None

        return handler_cls(
            self._config,
            path_info,
            input_file_format=file_format,
            **kwargs,
        )

    @staticmethod
    def create_repack_handler(
        config: PicoptSettings,
        unpack_handler: ContainerHandler,
    ) -> ContainerHandler:
        """Return a handler to repack the container using the optimized contents."""
        repack_handler_class: type[ContainerHandler] | None = (
            unpack_handler.repack_handler_class
        )
        if not repack_handler_class or (
            unpack_handler.__class__ is repack_handler_class and unpack_handler.CAN_PACK
        ):
            return unpack_handler
        return repack_handler_class(
            config,
            unpack_handler.path_info,
            input_file_format=repack_handler_class.OUTPUT_FILE_FORMAT,
            comment=unpack_handler.comment,
            optimized_contents=unpack_handler.get_optimized_contents(),
        )
