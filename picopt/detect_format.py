"""Detect file formats."""
from pathlib import Path
from typing import Callable
from typing import Optional
from typing import Set
from typing import Tuple

from PIL import Image
from PIL import ImageFile

from .extern import ExtArgs
from .formats.comic import Comic
from .formats.gif import Gif
from .settings import Settings


# Formats
NONE_FORMAT = "NONE"
ERROR_FORMAT = "ERROR"


def _is_program_selected(
    settings: Settings, progs: Tuple[Callable[[Settings, ExtArgs], str], ...]
) -> bool:
    """Determine if the program is enabled in the settings."""
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
    progs: Tuple[Callable[[Settings, ExtArgs], str], ...],
) -> bool:
    """Determine if the image format is selected by command line arguments."""
    intersection = formats & settings.formats
    mode = _is_program_selected(settings, progs)
    result = (image_format in intersection) and mode
    return result


def _is_image_sequenced(image: ImageFile) -> bool:
    """Determine if the image is a sequenced image."""
    try:
        image.seek(1)
        image.seek(0)
        result = True
    except EOFError:
        result = False

    return result


def get_image_format(settings: Settings, filename: Path) -> str:
    """Get the image format."""
    try:
        bad_image = Image.open(filename).verify()
        if bad_image:
            raise AttributeError
        image = Image.open(filename)
        image_format = str(image.format)
        if image_format == NONE_FORMAT:
            raise AttributeError
        sequenced = _is_image_sequenced(image)
        if sequenced:
            image_format = Gif.SEQUENCED_TEMPLATE.format(image_format)
    except (OSError, AttributeError):
        image_format = ERROR_FORMAT
        comic_format = Comic.get_comic_format(filename)
        if comic_format:
            image_format = comic_format
        if (
            (settings.verbose > 1)
            and image_format == ERROR_FORMAT
            and (not settings.list_only)
        ):
            print(filename, "doesn't look like an image or comic archive.")
    return image_format


def detect_file(settings: Settings, filename: Path) -> Optional[str]:
    """Decide what to do with the file."""
    image_format = get_image_format(settings, filename)

    if image_format in settings.formats:
        return image_format

    if image_format in (NONE_FORMAT, ERROR_FORMAT):
        return None

    if settings.verbose > 1 and not settings.list_only:
        print(
            filename, image_format, "is not a enabled image or " "comic archive type."
        )
    return None
