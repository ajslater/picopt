"""Return a handler for a path."""

from confuse.templates import AttrDict
from treestamps import Grovestamps

from picopt.formats import FileFormat
from picopt.handlers.container import ContainerHandler, PackingContainerHandler
from picopt.handlers.container.archive import ArchiveHandler
from picopt.handlers.handler import Handler
from picopt.handlers.metadata import PrepareInfoMixin
from picopt.path import PathInfo
from picopt.walk.detect_format import DetectFormat


class HandlerFactory(DetectFormat):
    """Handler factor for walker."""

    def _get_handler_class(
        self, file_format: FileFormat, key: str
    ) -> type[Handler] | None:
        format_handlers = self._config.computed.get(key)
        return format_handlers.get(file_format)

    def _create_handler_get_handler_class(
        self,
        file_format: FileFormat | None,
        *,
        convert: bool,
        repack: bool = False,
    ) -> type[Handler] | None:
        handler_cls: type[Handler] | None = None
        if file_format and file_format.format_str in self._config.formats:
            if convert and (not file_format.archive or repack):
                # For archives, conversion is done later with a different handler.
                # For images it's often faster to use the optimizer's binary to convert
                # instead of translating first with PIL.
                handler_cls = self._get_handler_class(file_format, "convert_handlers")
            if not handler_cls:
                handler_cls = self._get_handler_class(file_format, "native_handlers")
        if (
            repack
            and handler_cls
            and not issubclass(handler_cls, PackingContainerHandler)
        ):
            handler_cls = None
        return handler_cls

    def _get_repack_handler_class(
        self,
        path_info: PathInfo,
        file_format: FileFormat,
    ) -> type[PackingContainerHandler] | None:
        """Get the repack handler class or none if not configured."""
        repack_handler_class: type[PackingContainerHandler] | None = None
        try:
            repack_handler_class: type[PackingContainerHandler] | None = (  # type: ignore[reportAssignmentType]
                self._create_handler_get_handler_class(
                    file_format,
                    convert=path_info.convert,
                    repack=True,
                )
            )
        except OSError as exc:
            self._printer.warn(
                f"getting repack container handler for {path_info.full_output_name()}",
                exc,
            )
            from traceback import print_exc

            print_exc()
        if (
            not repack_handler_class
            and self._config.verbose > 1
            and not self._config.list_only
        ):
            fmt = str(file_format) if file_format else "unknown"
            self._printer.message(
                f"Skipped {path_info.full_output_name()}: ({fmt}) is not an enabled image or container.",
                attrs=["dark"],
            )

        return repack_handler_class

    def create_handler(
        self,
        path_info: PathInfo,
        timestamps: Grovestamps | None = None,
    ) -> Handler | None:
        """Return a handler for the image format."""
        # This is the consumer of config._format_handlers
        handler_cls: type[Handler] | None = None
        try:
            file_format, info = self.detect_format(path_info)
            handler_cls = self._create_handler_get_handler_class(
                file_format,
                convert=path_info.convert,
            )
        except OSError as exc:
            self._printer.warn(
                f"getting handler for {path_info.full_output_name()}", exc
            )
            from traceback import print_exc

            print_exc()
            file_format = None
            info = {}

        handler = None
        if handler_cls and file_format:
            kwargs = {}
            if issubclass(handler_cls, PrepareInfoMixin):
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
                    handler_cls = None

            if handler_cls:
                handler = handler_cls(
                    self._config,
                    path_info,
                    input_file_format=file_format,
                    **kwargs,
                )
        return handler

    def create_repack_handler(
        self,
        config: AttrDict,
        unpack_handler: ContainerHandler,
    ) -> PackingContainerHandler:
        """Return a handler to repack the container using optimized contents of the unpack handler."""
        # handler input_file_format is only for images so it doesn't matter what this is.
        repack_handler_class: type[PackingContainerHandler] = (
            unpack_handler.repack_handler_class
        )  # type: ignore[reportAssignmentType]
        if unpack_handler.__class__ == repack_handler_class and isinstance(
            unpack_handler, PackingContainerHandler
        ):
            handler = unpack_handler
        else:
            handler = repack_handler_class(
                config,
                unpack_handler.path_info,
                input_file_format=repack_handler_class.OUTPUT_FILE_FORMAT,
                comment=unpack_handler.comment,
                optimized_contents=unpack_handler.get_optimized_contents(),
                convert=True,
            )
        return handler
