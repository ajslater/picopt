from __future__ import print_function

try:
    from PIL import Image
except ImportError:
    import Image

import comic
from formats import gif
from settings import Settings

# Formats
NONE_FORMAT = 'NONE'
ERROR_FORMAT = 'ERROR'


def is_program_selected(progs):
    mode = False
    for prog in progs:
        if getattr(Settings, prog.__name__):
            mode = True
            break
    return mode


def is_format_selected(image_format, formats, progs):
    """returns a boolean indicating weather or not the image format
    was selected by the command line arguments"""
    intersection = formats & Settings.formats
    mode = is_program_selected(progs)
    result = (image_format in intersection) and mode
    return result


def is_image_sequenced(image):
    """determines if the image is a sequenced image"""
    try:
        image.seek(1)
        image.seek(0)
        result = True
    except EOFError:
        result = False

    return result


def get_image_format(filename):
    """gets the image format"""
    image = None
    bad_image = 1
    image_format = NONE_FORMAT
    sequenced = False
    try:
        bad_image = Image.open(filename).verify()
        image = Image.open(filename)
        image_format = image.format
        sequenced = is_image_sequenced(image)
    except (OSError, IOError, AttributeError):
        pass

    if sequenced:
        image_format = gif.SEQUENCED_TEMPLATE % image_format
    elif image is None or bad_image or image_format == NONE_FORMAT:
        image_format = ERROR_FORMAT
        comic_format = comic.get_comic_format(filename)
        if comic_format:
            image_format = comic_format
        if (Settings.verbose > 1) and image_format == ERROR_FORMAT and \
                (not Settings.list_only):
            print(filename, "doesn't look like an image or comic archive.")
    return image_format


def detect_file(filename):
    """decides what to do with the file"""
    image_format = get_image_format(filename)

    if image_format in Settings.formats:
        return image_format

    if image_format in (NONE_FORMAT, ERROR_FORMAT):
        return

    if Settings.verbose > 1 and not Settings.list_only:
        print(filename, image_format, 'is not a enabled image or '
              'comic archive type.')