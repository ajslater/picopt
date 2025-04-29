"""Detect file format."""

from collections.abc import Mapping
from contextlib import suppress
from typing import Any

from PIL import Image, UnidentifiedImageError
from PIL.TiffImagePlugin import TiffImageFile

from picopt.formats import (
    LOSSLESS_FORMAT_STRS,
    TIFF_LOSSLESS_COMPRESSION,
    FileFormat,
)
from picopt.handlers.container.archive.rar import (
    Cbr,
    Rar,
)
from picopt.handlers.container.archive.seven_zip import (
    Cb7,
    SevenZip,
)
from picopt.handlers.container.archive.tar import (
    Cbt,
    Tar,
    TarBz,
    TarGz,
    TarXz,
)
from picopt.handlers.container.archive.zip import (
    Cbz,
    EPub,
    Zip,
)
from picopt.handlers.image.svg import Svg
from picopt.handlers.image.webp import WebPLossless
from picopt.handlers.non_pil import NonPILIdentifier
from picopt.path import PathInfo
from picopt.pillow.webp_lossless import is_lossless
from picopt.walk.init import WalkInit

_NON_PIL_HANDLERS: tuple[type[NonPILIdentifier], ...] = (
    Svg,
    Cbz,
    Zip,
    Cbr,
    Rar,
    EPub,
    SevenZip,
    Cb7,
    TarGz,
    TarBz,
    TarXz,
    Cbt,
    Tar,  # must be after other tars to detect properly
)


def _extract_image_info(
    path_info: PathInfo, *, keep_metadata: bool
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
            fp.close()  # type: ignore[reportAttributeAccessIssue]
        fp = path_info.path_or_buffer()
        with Image.open(fp) as image:
            image_format_str = image.format
            if image_format_str:
                # It's a rare thing if an info key is an int tuple?
                info: dict[str, Any] = image.info if keep_metadata else {}  # type: ignore[reportAssignmentType]
                animated = getattr(image, "is_animated", False)
                info["animated"] = animated
                if animated and (n_frames := getattr(image, "n_frames", None)):
                    info["n_frames"] = n_frames
                with suppress(AttributeError):
                    info["mpinfo"] = image.mpinfo  # type: ignore[reportAttributeAccessIssue]
        image.close()  # for animated images
        with suppress(AttributeError):
            fp.close()  # type: ignore[reportAttributeAccessIssue]
    except UnidentifiedImageError:
        pass
    return image_format_str, info


def _is_lossless(
    image_format_str: str,
    path_info: PathInfo,
    info: Mapping[str, Any],
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
    path_info: PathInfo, *, keep_metadata: bool
) -> tuple[FileFormat | None, Mapping[str, Any]]:
    """Construct the image format with PIL."""
    image_format_str, info = _extract_image_info(path_info, keep_metadata=keep_metadata)

    file_format = None
    if image_format_str:
        lossless = _is_lossless(image_format_str, path_info, info)
        file_format = FileFormat(
            image_format_str, lossless, info.get("animated", False)
        )
    return file_format, info


def _get_non_pil_format(path_info: PathInfo) -> FileFormat | None:
    """Get the container format by querying each handler."""
    for handler in _NON_PIL_HANDLERS:
        if file_format := handler.identify_format(path_info):
            break
    else:
        file_format = None
    return file_format


class DetectFormat(WalkInit):
    """Detect format method."""

    def detect_format(
        self, path_info: PathInfo
    ) -> tuple[FileFormat | None, Mapping[str, Any]]:
        """Return the format and updated pathinfo."""
        file_format, info = _get_image_format(
            path_info, keep_metadata=self._config.keep_metadata
        )
        if not file_format:
            file_format = _get_non_pil_format(path_info)
        return file_format, info
