"""Detect file formats."""
from pathlib import Path
from typing import Callable, Optional, Set, Tuple

from PIL import Image

from picopt.extern import ExtArgs
from picopt.formats.comic import Comic
from picopt.formats.format import ANIMATED_FORMAT_PREFIX
from picopt.settings import Settings


def _is_program_selected(
    settings: Settings, progs: Tuple[Callable[[ExtArgs], str], ...]
) -> bool:
    """Determine if any of the program is enabled in the settings."""
    mode = False
    for prog in progs:
        if getattr(settings, prog.__func__.__name__):  # type: ignore
            mode = True
            break
    return mode


def is_format_selected(
    settings: Settings,
    image_format: str,
    formats: Set[str],
    progs: Tuple[Callable[[ExtArgs], str], ...],
) -> bool:
    """Determine if the image format is selected by command line arguments."""
    intersection = formats & settings.formats
    mode = _is_program_selected(settings, progs)
    result = (image_format in intersection) and mode
    return result


def _get_image_format(path: Path) -> Optional[str]:
    """Get the image format."""
    image_format: Optional[str] = None
    try:
        with Image.open(path) as image:
            image_format = image.format
            try:
                if image_format and image.is_animated:
                    image_format = ANIMATED_FORMAT_PREFIX + image_format
            except AttributeError:
                pass
            image.verify()  # need to reopen after verify() so its last
    except (OSError, AttributeError):
        image_format = Comic.get_comic_format(path)
    return image_format


def detect_file(settings: Settings, path: Path) -> Optional[str]:
    """Decide what to do with the file."""
    image_format = _get_image_format(path)
    if image_format not in settings.formats:
        image_format = None
        if settings.verbose > 2 and not settings.list_only:
            print(
                path, image_format, "is not an enabled image or " "comic archive type."
            )
    return image_format
