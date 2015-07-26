import os
import rarfile
import zipfile

try:
    from PIL import Image
except ImportError:
    import Image

import jpeg
import gif
import png
import comic

# Formats
FORMAT_DELIMETER = ','
DEFAULT_FORMATS = 'ALL'
ALL_DEFAULT_FORMATS = jpeg.JPEG_FORMATS | gif.GIF_FORMATS | \
                      png.PNG_CONVERTABLE_FORMATS
ALL_FORMATS = ALL_DEFAULT_FORMATS | comic.COMIC_FORMATS
NONE_FORMAT = 'NONE'
ERROR_FORMAT = 'ERROR'


def is_format_selected(image_format, formats, arguments, mode):
    """returns a boolean indicating weather or not the image format
    was selected by the command line arguments"""
    intersection = formats & arguments.formats
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


def get_image_format(filename, arguments):
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
        filename_ext = os.path.splitext(filename)[-1].lower()
        if filename_ext in comic.COMIC_EXTS:
            if zipfile.is_zipfile(filename):
                image_format = comic.CBZ_FORMAT
            elif rarfile.is_rarfile(filename):
                image_format = comic.CBR_FORMAT
        if (arguments.verbose > 1) and image_format == ERROR_FORMAT and \
                (not arguments.list_only):
            print(filename, "doesn't look like an image or comic archive.")
    return image_format


def detect_file(filename, arguments):
    """decides what to do with the file"""
    image_format = get_image_format(filename, arguments)

    if image_format in arguments.formats:
        return image_format

    if image_format in (NONE_FORMAT, ERROR_FORMAT):
        return

    if arguments.verbose > 1 and not arguments.list_only:
        print(filename, image_format, 'is not a enabled image or '
              'comic archive type.')
