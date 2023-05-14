"""Return a handler for a path."""
from pathlib import Path
from typing import Optional

from confuse.templates import AttrDict
from PIL import Image, UnidentifiedImageError
from termcolor import cprint

from picopt.config import WEBP_CONVERTABLE_FORMAT_STRS
from picopt.data import PathInfo
from picopt.handlers.container import ContainerHandler
from picopt.handlers.handler import FileFormat, Handler, Metadata
from picopt.handlers.image import TIFF_FORMAT_STR
from picopt.handlers.webp import WebPLossless
from picopt.handlers.zip import CBR, CBZ, EPub, Rar, Zip
from picopt.pillow.webp_lossless import is_lossless

_ALWAYS_LOSSLESS_FORMAT_STRS = WEBP_CONVERTABLE_FORMAT_STRS - {TIFF_FORMAT_STR}
_CONTAINER_HANDLERS: tuple[type[ContainerHandler], ...] = (CBZ, Zip, CBR, Rar, EPub)


def _is_lossless(image_format: str, path: Path, info: dict) -> bool:
    """Determine if image format is lossless."""
    if image_format in _ALWAYS_LOSSLESS_FORMAT_STRS:
        lossless = True
    elif image_format == WebPLossless.OUTPUT_FORMAT_STR:
        lossless = is_lossless(str(path))
    elif image_format == TIFF_FORMAT_STR:
        lossless = info.get("compression") != "jpeg"
    else:
        lossless = False
    return lossless


def _extract_image_info(path, keep_metadata):
    """Get image format and info from a file."""
    image_format_str = None
    info = {}
    n_frames = 1
    animated = False
    try:
        with Image.open(path, mode="r") as image:
            image.verify()
        image.close()  # for animated images
        with Image.open(path, mode="r") as image:
            image_format_str = image.format
            if image_format_str:
                animated = getattr(image, "is_animated", False)
                info = image.info
                if keep_metadata and animated:
                    n_frames = getattr(image, "n_frames", 1)
        image.close()  # for animated images
    except UnidentifiedImageError:
        pass
    return image_format_str, info, n_frames, animated


def _get_image_format(
    path: Path, keep_metadata: bool
) -> tuple[Optional[FileFormat], Metadata]:
    """Construct the image format with PIL."""
    image_format_str, info, n_frames, animated = _extract_image_info(
        path, keep_metadata
    )

    file_format = None
    metadata = Metadata()
    if image_format_str:
        if keep_metadata:
            exif = info.get("exif", b"")
            icc = info.get("icc_profile", "")
            metadata = Metadata(exif, icc, n_frames)
        lossless = _is_lossless(image_format_str, path, info)
        file_format = FileFormat(image_format_str, lossless, animated)
    return file_format, metadata


def _get_container_format(path: Path) -> Optional[FileFormat]:
    """Get the container format by querying each handler."""
    file_format = None
    for container_handler in _CONTAINER_HANDLERS:
        file_format = container_handler.identify_format(path)
        if file_format is not None:
            break
    return file_format


def _get_handler_class(
    config: AttrDict, key: str, file_format: FileFormat
) -> Optional[type[Handler]]:
    handler_classes = config.computed.format_handlers.get(file_format)
    return handler_classes.get(key) if handler_classes else None


def _create_handler_get_format(
    config: AttrDict, path: Path
) -> tuple[Optional[FileFormat], Metadata]:
    file_format, metadata = _get_image_format(path, config.keep_metadata)
    if not file_format:
        file_format = _get_container_format(path)
    return file_format, metadata


def _create_handler_get_handler_class(
    config: AttrDict, convert: bool, file_format: Optional[FileFormat]
) -> Optional[type[Handler]]:
    handler_cls: Optional[type[Handler]] = None
    if not file_format:
        return handler_cls
    if convert:
        handler_cls = _get_handler_class(config, "convert", file_format)
    if not handler_cls:
        handler_cls = _get_handler_class(config, "native", file_format)
    return handler_cls


def _create_handler_no_handler_class(
    config: AttrDict, path: Path, file_format: Optional[FileFormat]
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


def create_handler(config: AttrDict, path_info: PathInfo) -> Optional[Handler]:
    """Get the image format."""
    # This is the consumer of config._format_handlers
    file_format: Optional[FileFormat] = None
    metadata: Metadata = Metadata()
    handler_cls: Optional[type[Handler]] = None
    try:
        file_format, metadata = _create_handler_get_format(config, path_info.path)
        handler_cls = _create_handler_get_handler_class(
            config, path_info.convert, file_format
        )
    except OSError as exc:
        cprint(f"WARNING: getting handler {exc}", "yellow")

    if handler_cls and file_format is not None:
        handler = handler_cls(config, path_info, file_format, metadata)
    else:
        handler = _create_handler_no_handler_class(config, path_info.path, file_format)
    return handler
