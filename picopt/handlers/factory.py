"""Return a handler for a path."""
from collections.abc import Mapping
from contextlib import suppress
from typing import Any

from confuse.templates import AttrDict
from PIL import Image, UnidentifiedImageError
from PIL.JpegImagePlugin import JpegImageFile
from PIL.PngImagePlugin import PngImageFile
from PIL.TiffImagePlugin import XMP as TIFF_XMP_TAG
from PIL.TiffImagePlugin import TiffImageFile
from termcolor import cprint

from picopt.formats import (
    LOSSLESS_FORMAT_STRS,
    PNGINFO_XMP_KEY,
    TIFF_LOSSLESS_COMPRESSION,
    FileFormat,
)
from picopt.handlers.handler import Handler
from picopt.handlers.non_pil import NonPILIdentifier
from picopt.handlers.svg import Svg
from picopt.handlers.webp import WebPLossless
from picopt.handlers.zip import Cbr, Cbz, EPub, Rar, Zip
from picopt.path import PathInfo
from picopt.pillow.jpeg_xmp import get_jpeg_xmp
from picopt.pillow.webp_lossless import is_lossless

###################
# Get File Format #
###################
_NON_PIL_HANDLERS: tuple[type[NonPILIdentifier], ...] = (
    Svg,
    Cbz,
    Zip,
    Cbr,
    Rar,
    EPub,
)


def _set_xmp(keep_metadata: bool, image: Image.Image, info: dict) -> None:
    """Extract and set XMP info in the info dict."""
    # Pillow's only extracts raw xmp data into the info dict sometimes for some formats.
    # Pillow's support for writing xmp data is very different between PNG & WEBP.
    if not keep_metadata or "xmp" in info:
        return
    try:
        xmp = None
        if image.format == JpegImageFile.format:
            xmp = get_jpeg_xmp(image)  # type: ignore
        elif image.format == PngImageFile.format:
            xmp = info.get(PNGINFO_XMP_KEY)
        if isinstance(image, TiffImageFile):
            # elif image.format == TiffImageFile.format:
            xmp = image.tag_v2.get(TIFF_XMP_TAG)
        if xmp:
            info["xmp"] = xmp
    except Exception:
        cprint("Failed to extract xmp data:")


def _extract_image_info(
    path_info: PathInfo, keep_metadata: bool
) -> tuple[str | None, dict[str, Any]]:
    """Get image format and info from a file."""
    image_format_str = None
    info = {}
    n_frames = 1
    animated = False
    try:
        fp = path_info.path_or_buffer()
        with Image.open(fp) as image:
            image.verify()
        image.close()  # for animated images
        with suppress(AttributeError):
            fp.close()  # type: ignore
        fp = path_info.path_or_buffer()
        with Image.open(fp) as image:
            image_format_str = image.format
            if image_format_str:
                info = image.info if keep_metadata else {}
                animated = getattr(image, "is_animated", False)
                info["animated"] = animated
                if animated:
                    n_frames = image.n_frames
                    if n_frames is not None:
                        info["n_frames"] = n_frames
                try:
                    _set_xmp(keep_metadata, image, info)
                except Exception as exc:
                    cprint(
                        f"WARNING: Failed to extract xmp data for {path_info.full_name()}, {exc}",
                        "yellow",
                    )
                with suppress(AttributeError):
                    info["mpinfo"] = image.mpinfo  # type: ignore
        image.close()  # for animated images
        with suppress(AttributeError):
            fp.close()  # type: ignore
    except UnidentifiedImageError:
        pass
    return image_format_str, info


def _is_lossless(
    image_format_str: str, path_info: PathInfo, info: Mapping[str, Any]
) -> bool:
    """Determine if image format is lossless."""
    if image_format_str == WebPLossless.OUTPUT_FORMAT_STR:
        lossless = is_lossless(path_info.fp_or_buffer())
    elif image_format_str == TiffImageFile.format:
        lossless = info.get("compression") in TIFF_LOSSLESS_COMPRESSION
    else:
        lossless = image_format_str in LOSSLESS_FORMAT_STRS
    return lossless


def _get_image_format(
    path_info: PathInfo, keep_metadata: bool
) -> tuple[FileFormat | None, Mapping[str, Any]]:
    """Construct the image format with PIL."""
    image_format_str, info = _extract_image_info(path_info, keep_metadata)

    file_format = None
    if image_format_str:
        lossless = _is_lossless(image_format_str, path_info, info)
        file_format = FileFormat(
            image_format_str, lossless, info.get("animated", False)
        )
    return file_format, info


def _get_non_pil_format(path_info: PathInfo) -> FileFormat | None:
    """Get the container format by querying each handler."""
    file_format = None
    for handler in _NON_PIL_HANDLERS:
        file_format = handler.identify_format(path_info)
        if file_format is not None:
            break
    else:
        file_format = None
    return file_format


def _create_handler_get_format(
    config: AttrDict, path_info: PathInfo
) -> tuple[FileFormat | None, Mapping[str, Any]]:
    file_format, info = _get_image_format(path_info, config.keep_metadata)
    if not file_format:
        file_format = _get_non_pil_format(path_info)
    return file_format, info


#####################
# Get Handler Class #
#####################
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


####################
# No Handler Class #
####################
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
        file_format, info = _create_handler_get_format(config, path_info)
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
