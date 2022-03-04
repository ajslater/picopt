"""Return a handler for a path."""
from pathlib import Path
from typing import Optional, Tuple, Type

from confuse.templates import AttrDict
from PIL import Image, UnidentifiedImageError

from picopt.config import WEBP_CONVERTABLE_FORMATS
from picopt.handlers.container import ContainerHandler
from picopt.handlers.handler import Format, Handler, Metadata
from picopt.handlers.image import TIFF_FORMAT
from picopt.handlers.webp import WebPLossless
from picopt.handlers.zip import CBZ, EPub, Zip
from picopt.pillow.webp_lossless import is_lossless


_ALWAYS_LOSSLESS_FORMATS = WEBP_CONVERTABLE_FORMATS - set([TIFF_FORMAT])
_CONTAINER_HANDLERS: Tuple[Type[ContainerHandler], ...] = (CBZ, Zip, EPub)


def _is_lossless(image_format: str, path: Path, info: dict) -> bool:
    """Determine if image format is lossless."""
    if image_format in _ALWAYS_LOSSLESS_FORMATS:
        lossless = True
    elif image_format == WebPLossless.OUTPUT_FORMAT:
        lossless = is_lossless(str(path))
    elif image_format == TIFF_FORMAT:
        lossless = info.get("compression") != "jpeg"
    else:
        lossless = False
    return lossless


def _get_image_format(
    path: Path, destroy_metadata: bool
) -> Tuple[Optional[Format], Metadata]:
    """Construct the image format with PIL."""
    format = None
    metadata = Metadata()
    n_frames = 1
    try:
        with Image.open(path, mode="r") as image:
            image.verify()
        with Image.open(path, mode="r") as image:
            image_format = image.format
            if image_format is None:
                raise UnidentifiedImageError("No image format")
            animated = getattr(image, "is_animated", False)
            info = image.info
            if not destroy_metadata and animated:
                n_frames = getattr(image, "n_frames", 1)
        if not destroy_metadata:
            exif = info.get("exif", b"")
            icc = info.get("icc_profile", "")
            metadata = Metadata(exif, icc, n_frames)
        lossless = _is_lossless(image_format, path, info)
        format = Format(image_format, lossless, animated)
    except UnidentifiedImageError:
        pass
    return format, metadata


def _get_container_format(path: Path) -> Optional[Format]:
    """Get the container format by querying each handler."""
    format = None
    for container_handler in _CONTAINER_HANDLERS:
        format = container_handler.identify_format(path)
        if format is not None:
            break
    return format


def create_handler(config: AttrDict, path: Path) -> Optional[Handler]:
    """Get the image format."""
    format: Optional[Format] = None
    metadata: Metadata = Metadata()
    handler_cls: Optional[Type[Handler]] = None
    try:
        format, metadata = _get_image_format(path, config.destroy_metadata)
        if not format:
            format = _get_container_format(path)
        handler_cls = config._format_handlers.get(format)
    except OSError as exc:
        print(exc)

    if handler_cls and format is not None:
        handler = handler_cls(config, path, format, metadata)
    else:
        if config.verbose > 2 and not config.list_only:
            print(
                path,
                "is not an enabled image or container.",
            )
        handler = None
    return handler
