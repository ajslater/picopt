"""Return a handler for a path."""

from confuse.templates import AttrDict
from termcolor import cprint

from picopt.formats import FileFormat
from picopt.handlers.detect_format import detect_format
from picopt.handlers.handler import Handler
from picopt.path import PathInfo


def _get_handler_class(
    config: AttrDict, file_format: FileFormat, key: str
) -> type[Handler] | None:
    format_handlers = config.computed.get(key)
    return format_handlers.get(file_format)


def _create_handler_get_handler_class(
    config: AttrDict, convert: bool, file_format: FileFormat | None
) -> type[Handler] | None:
    handler_cls: type[Handler] | None = None
    if file_format and file_format.format_str in config.formats:
        if convert:
            handler_cls = _get_handler_class(config, file_format, "convert_handlers")
        if not handler_cls:
            handler_cls = _get_handler_class(config, file_format, "native_handlers")
    return handler_cls


def _create_handler_no_handler_class(
    config: AttrDict, path_info: PathInfo, file_format: FileFormat | None
) -> None:
    if config.verbose > 1 and not config.list_only:
        if file_format:
            fmt = file_format.format_str
            if file_format.lossless:
                fmt += " lossless"
            else:
                fmt += " lossy"
            if file_format.animated:
                fmt += " animated"
        else:
            fmt = "unknown"
        cprint(
            f"Skipped {path_info.full_name()}: ({fmt}) is not an enabled image or container.",
            "white",
            attrs=["dark"],
        )
    else:
        cprint(".", "white", attrs=["dark"], end="")


def create_handler(config: AttrDict, path_info: PathInfo) -> Handler | None:
    """Get the image format."""
    # This is the consumer of config._format_handlers
    handler_cls: type[Handler] | None = None
    try:
        file_format, info = detect_format(config, path_info)
        handler_cls = _create_handler_get_handler_class(
            config, path_info.convert, file_format
        )
    except OSError as exc:
        cprint(f"WARNING: getting handler {exc}", "yellow")
        from traceback import print_exc

        print_exc()
        file_format = None
        info = {}

    if handler_cls and file_format is not None:
        handler = handler_cls(config, path_info, file_format, info)
    else:
        handler = _create_handler_no_handler_class(config, path_info, file_format)
    return handler
