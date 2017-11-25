"""Optimize a file."""
from __future__ import absolute_import, division, print_function

import os
import shutil
import traceback

from . import PROGRAM_NAME, detect_format, files, stats
from .extern import ExtArgs
from .formats import gif, jpeg, png
from .settings import Settings

TMP_SUFFIX = '.{}-optimized'.format(PROGRAM_NAME)

Settings.formats = png.CONVERTABLE_FORMATS | jpeg.FORMATS | gif.FORMATS
Settings.to_png_formats = png.CONVERTABLE_FORMATS


def _optimize_image_external(filename, func, image_format, new_ext):
    """Optimize the file with the external function."""
    new_filename = filename + TMP_SUFFIX + new_ext
    new_filename = os.path.normpath(new_filename)
    shutil.copy2(filename, new_filename)

    ext_args = ExtArgs(filename, new_filename)
    new_image_format = func(ext_args)

    report_stats = files.cleanup_after_optimize(filename, new_filename,
                                                image_format,
                                                new_image_format)
    percent = stats.new_percent_saved(report_stats)
    if percent != 0:
        report = '{}: {}'.format(func.__name__, percent)
    else:
        report = ''
    report_stats.report_list.append(report)

    return report_stats


def _optimize_with_progs(format_module, filename, image_format):
    """
    Use the correct optimizing functions in sequence.

    And report back statistics.
    """
    filesize_in = os.stat(filename).st_size
    report_stats = None

    for func in format_module.PROGRAMS:
        if not getattr(Settings, func.__name__):
            continue
        report_stats = _optimize_image_external(
            filename, func, image_format, format_module.OUT_EXT)
        filename = report_stats.final_filename
        if format_module.BEST_ONLY:
            break

    if report_stats is not None:
        report_stats.bytes_in = filesize_in
    else:
        report_stats = stats.skip(image_format, filename)

    return report_stats


def _get_format_module(image_format):
    """Get the format module to use for optimizing the image."""
    format_module = None
    nag_about_gifs = False

    if detect_format.is_format_selected(image_format,
                                        Settings.to_png_formats,
                                        png.PROGRAMS):
        format_module = png
    elif detect_format.is_format_selected(image_format, jpeg.FORMATS,
                                          jpeg.PROGRAMS):
        format_module = jpeg
    elif detect_format.is_format_selected(image_format, gif.FORMATS,
                                          gif.PROGRAMS):
        # this captures still GIFs too if not caught above
        format_module = gif
        nag_about_gifs = True

    return format_module, nag_about_gifs


def optimize_image(arg):
    """Optimize a given image from a filename."""
    try:
        filename, image_format, settings = arg

        Settings.update(settings)

        format_module, nag_about_gifs = _get_format_module(image_format)

        if format_module is None:
            if Settings.verbose > 1:
                print(filename, image_format)  # image.mode)
                print("\tFile format not selected.")
            return

        report_stats = _optimize_with_progs(format_module, filename,
                                            image_format)
        report_stats.nag_about_gifs = nag_about_gifs
        stats.report_saved(report_stats)
        return report_stats
    except Exception as exc:
        print(exc)
        traceback.print_exc(exc)
        raise exc
