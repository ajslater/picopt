"""Detect file handlers."""
from pathlib import Path
from typing import Optional, Tuple, Type

from confuse.templates import AttrDict
from PIL import Image, UnidentifiedImageError

from picopt import config
from picopt.handlers.container import ContainerHandler
from picopt.handlers.handler import Format, Handler
from picopt.handlers.webp import WebPLossless
from picopt.handlers.zip import CBZ, Zip
from picopt.pillow.webp_lossless import is_lossless


_ALWAYS_LOSSLESS_FORMAT_STRS = config.WEBP_CONVERTABLE_FORMAT_STRS
_CONTAINER_HANDLERS: Tuple[Type[ContainerHandler], ...] = (CBZ, Zip)


def _get_format(path) -> Optional[Format]:
    format = None
    try:
        with Image.open(path) as image:
            image_format = image.format
            if image_format is None:
                raise ValueError("No image format")
            try:
                animated = image.is_animated
            except AttributeError:
                animated = False
            image.verify()  # seeks to end of image. must be last.
        if image_format in _ALWAYS_LOSSLESS_FORMAT_STRS:
            lossless = True
        elif image_format == WebPLossless.FORMAT_STR:
            lossless = is_lossless(str(path))
        else:
            lossless = False
        format = Format(image_format, lossless, animated)
    except UnidentifiedImageError:
        pass
    return format


def _get_container_format(path) -> Optional[Format]:
    format = None
    for container_handler in _CONTAINER_HANDLERS:
        format = container_handler.can_handle(path)
        if format is not None:
            break
    return format


def get_handler(config: AttrDict, path: Path) -> Optional[Handler]:
    """Get the image format."""
    format: Optional[Format] = None
    handler_cls: Optional[Type[Handler]] = None
    try:
        format = _get_format(path)
        if not format:
            format = _get_container_format(path)
        print(f"{format=}")
        handler_cls = config._format_handlers.get(format)
    except OSError as exc:
        print(exc)
        pass

    print(f"{handler_cls=}")
    if handler_cls and format is not None:
        handler = handler_cls(config, path, format)
    else:
        if config.verbose > 2 and not config.list_only:
            print(
                path,
                "is not an enabled image or container.",
            )
        handler = None
    return handler
