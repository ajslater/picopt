"""Return a handler for a path."""
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from confuse.templates import AttrDict
from PIL import Image, UnidentifiedImageError
from termcolor import cprint

from picopt.data import PathInfo
from picopt.handlers.container import ContainerHandler
from picopt.handlers.convertible import (
    LOSSLESS_FORMAT_STRS,
    TIFF_FORMAT_STR,
    TIFF_LOSSLESS_COMPRESSION,
)
from picopt.handlers.handler import FileFormat, Handler
from picopt.handlers.png_animated import PngAnimated
from picopt.handlers.svg import Svg
from picopt.handlers.webp import WebPLossless
from picopt.handlers.webp_animated import WebPAnimatedLossless
from picopt.handlers.zip import Cbr, Cbz, EPub, Rar, Zip
from picopt.pillow.webp_lossless import is_lossless

_CONTAINER_HANDLERS: tuple[type[ContainerHandler], ...] = (
    Cbz,
    Zip,
    Cbr,
    Rar,
    EPub,
    PngAnimated,
    WebPAnimatedLossless,
)


def _extract_image_info(
    path: Path, keep_metadata: bool
) -> tuple[str | None, dict[str, Any]]:
    """Get image format and info from a file."""
    image_format_str = None
    info = {}
    n_frames = 1
    animated = False
    try:
        lower_suffix = path.suffix.lower()
        if lower_suffix == Svg.INPUT_FORMAT_SUFFIX:
            image_format_str = Svg.OUTPUT_FORMAT_STR
        else:
            with Image.open(path, mode="r") as image:
                image.verify()
            image.close()  # for animated images
            with Image.open(path, mode="r") as image:
                image_format_str = image.format
                if image_format_str:
                    info = image.info if keep_metadata else {}
                    animated = getattr(image, "is_animated", False)
                    info["animated"] = animated
                    if animated:
                        n_frames = image.n_frames
                        if n_frames is not None:
                            info["n_frames"] = n_frames
            image.close()  # for animated images
    except UnidentifiedImageError:
        pass
    return image_format_str, info


def _is_lossless(image_format_str: str, path: Path, info: Mapping[str, Any]) -> bool:
    """Determine if image format is lossless."""
    if image_format_str == WebPLossless.OUTPUT_FORMAT_STR:
        lossless = is_lossless(str(path))
    elif image_format_str == TIFF_FORMAT_STR:
        lossless = info.get("compression") in TIFF_LOSSLESS_COMPRESSION
    else:
        lossless = image_format_str in LOSSLESS_FORMAT_STRS
    return lossless


def _get_image_format(
    path: Path, keep_metadata: bool
) -> tuple[FileFormat | None, Mapping[str, Any]]:
    """Construct the image format with PIL."""
    image_format_str, info = _extract_image_info(path, keep_metadata)

    file_format = None
    if image_format_str:
        lossless = _is_lossless(image_format_str, path, info)
        file_format = FileFormat(
            image_format_str, lossless, info.get("animated", False)
        )
    return file_format, info


def _get_container_format(path: Path) -> FileFormat | None:
    """Get the container format by querying each handler."""
    file_format = None
    for container_handler in _CONTAINER_HANDLERS:
        file_format = container_handler.identify_format(path)
        if file_format is not None:
            break
    return file_format


def _get_handler_class(
    config: AttrDict, file_format: FileFormat, key: str
) -> type[Handler] | None:
    format_handlers = config.computed.get(key)
    return format_handlers.get(file_format)


def _create_handler_get_format(
    config: AttrDict, path: Path
) -> tuple[FileFormat | None, Mapping[str, Any]]:
    file_format, info = _get_image_format(path, config.keep_metadata)
    if not file_format:
        file_format = _get_container_format(path)
    return file_format, info


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
    config: AttrDict, path: Path, file_format: FileFormat | None
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
            f"Skipped {path}: ({fmt}) is not an enabled image or container.",
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
        file_format, info = _create_handler_get_format(config, path_info.path)
        handler_cls = _create_handler_get_handler_class(
            config, path_info.convert, file_format
        )
    except OSError as exc:
        cprint(f"WARNING: getting handler {exc}", "yellow")
        file_format = None
        info = {}

    if handler_cls and file_format is not None:
        handler = handler_cls(config, path_info, file_format, info)
    else:
        handler = _create_handler_no_handler_class(config, path_info.path, file_format)
    return handler
