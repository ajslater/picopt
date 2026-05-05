"""
Detect file format.

Two-phase dispatch:


1. **PIL probe** — try to open the file as an image. If PIL recognises it,
   build a :class:`FileFormat` from the PIL format string and the info dict.
   Two formats need extra disambiguation that PIL doesn't do for us:

   * WebP can be either lossless or lossy at the same format string;
     :func:`picopt.pillow.webp_lossless.is_lossless` reads the raw chunk
     header to decide.
   * TIFF lossless-vs-lossy depends on the ``compression`` info key;
     :func:`picopt.plugins.pil_convertible.is_tiff_lossless` owns the
     codec set.

   Every other PIL format string is checked against
   :func:`registry.lossless_format_strs`.

2. **Non-PIL detectors** — if PIL didn't recognise the file, walk the
   priority-ordered detector list from :func:`registry.detectors`. The
   first detector to return a :class:`FileFormat` wins. Detector ordering
   (e.g. ``TarGz`` must run before plain ``Tar``) lives next to each
   plugin via ``Detector.PRIORITY`` rather than as a hand-ordered list
   here.
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any

from PIL import Image, UnidentifiedImageError

from picopt import plugins as registry
from picopt.pillow.webp_lossless import is_lossless as _webp_is_lossless
from picopt.plugins.base.format import FileFormat
from picopt.plugins.pil_convertible import is_tiff_lossless

if TYPE_CHECKING:
    from collections.abc import Mapping

    from PIL.ImageFile import ImageFile

    from picopt.path import PathInfo

# PIL format-string constants. Hardcoded so this module doesn't have to
# import the per-format PIL ImageFile subclasses just to read a string.
_TIFF_FORMAT_STR = "TIFF"
_WEBP_FORMAT_STR = "WEBP"


def _extract_image_info_from_image(
    image: ImageFile, info: dict[str, Any], *, keep_metadata: bool
) -> None:
    image_format_str = image.format
    if not image_format_str:
        return
    if keep_metadata:
        str_md = {
            key: value for key, value in image.info.items() if isinstance(key, str)
        }
        info.update(str_md)

    animated = getattr(image, "is_animated", False)
    info["animated"] = animated
    if animated and (n_frames := getattr(image, "n_frames", 0)):
        info["n_frames"] = n_frames
    with suppress(AttributeError):
        info["mpinfo"] = image.mpinfo  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]


def _extract_image_info(
    path_info: PathInfo, *, keep_metadata: bool
) -> tuple[str | None, dict[str, Any]]:
    """Get image format and info from a file via PIL."""
    image_format_str: str | None = None
    info: dict[str, Any] = {}
    try:
        # Read metadata before verify(): for some Path-opened formats
        # (notably GIF), PIL closes its internal fp during verify(), which
        # then breaks lazy attrs like is_animated and n_frames.
        with Image.open(path_info.path_or_buffer()) as image:
            image_format_str = image.format
            _extract_image_info_from_image(image, info, keep_metadata=keep_metadata)
            image.verify()
    except UnidentifiedImageError:
        pass
    return image_format_str, info


def _is_lossless(
    image_format_str: str,
    path_info: PathInfo,
    info: Mapping[str, Any],
) -> bool:
    """Decide whether a PIL-identified format is the lossless variant."""
    if image_format_str == _WEBP_FORMAT_STR:
        return _webp_is_lossless(path_info.fp_or_buffer())
    if image_format_str == _TIFF_FORMAT_STR:
        return is_tiff_lossless(dict(info))
    return image_format_str in registry.lossless_format_strs()


def _get_image_format(
    path_info: PathInfo, *, keep_metadata: bool
) -> tuple[FileFormat | None, Mapping[str, Any]]:
    """PIL phase: identify the image and build its FileFormat."""
    image_format_str, info = _extract_image_info(path_info, keep_metadata=keep_metadata)
    if not image_format_str:
        return None, info
    file_format = FileFormat(
        image_format_str,
        lossless=_is_lossless(image_format_str, path_info, info),
        animated=info.get("animated", False),
    )
    return file_format, info


def _get_non_pil_format(path_info: PathInfo) -> FileFormat | None:
    """Non-PIL phase: try every plugin-supplied detector in priority order."""
    for detector in registry.detectors():
        if file_format := detector.identify(path_info):
            return file_format
    return None


def detect_format(
    path_info: PathInfo, *, keep_metadata: bool
) -> tuple[FileFormat | None, Mapping[str, Any]]:
    """Return the file format (or None) and the PIL info dict."""
    file_format, info = _get_image_format(path_info, keep_metadata=keep_metadata)
    if not file_format:
        file_format = _get_non_pil_format(path_info)
    return file_format, info
