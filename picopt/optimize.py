"""Optimize a file."""
from __future__ import print_function
from collections import namedtuple
import os
import shutil
import traceback

from . import detect_format
from .formats import (
    gif,
    jpeg,
    png
)
from . import PROGRAM_NAME
from .settings import Settings
from . import stats
from . import files


NEW_EXT = '.%s-optimized.png' % PROGRAM_NAME


ExtArgs = namedtuple('ExtArgs', ['old_filename', 'new_filename'])

Settings.formats = png.CONVERTABLE_FORMATS | jpeg.FORMATS | gif.FORMATS
Settings.to_png_formats = png.CONVERTABLE_FORMATS


def _optimize_image_external(filename, func, image_format):
    """Optimize the file with the external function."""
    new_filename = os.path.normpath(filename + NEW_EXT)
    shutil.copy2(filename, new_filename)

    ext_args = ExtArgs._make([filename, new_filename])
    func(ext_args)
    # XXX this could be gotten from func
    new_image_format = detect_format.get_image_format(new_filename)

    report_stats = files.cleanup_after_optimize(filename, new_filename,
                                                image_format, new_image_format)
    percent = stats.new_percent_saved(report_stats)
    if percent != 0:
        report = '%s: %s' % (func.__name__, percent)
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
        report_stats = _optimize_image_external(filename, func, image_format)
        filename = report_stats.final_filename
        if format_module.BEST_ONLY:
            break

    if report_stats is not None:
        report_stats.bytes_diff['in'] = filesize_in
    else:
        report_stats = stats.skip(image_format, filename)

    return report_stats


def _get_format_module(image_format, nag_about_gifs):
    """Get the format module to use for optimizing the image."""
    format_module = None

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
        nag_about_gifs.set(True)

    return format_module


def optimize_image(arg):
    """Optimize a given image from a filename."""
    try:
        filename, image_format, settings, total_bytes_in, total_bytes_out, \
            nag_about_gifs = arg

        Settings.update(settings)

        format_module = _get_format_module(image_format, nag_about_gifs)

        if format_module is None:
            if Settings.verbose > 1:
                print(filename, image_format)  # image.mode)
                print("\tFile format not selected.")
            return

        report_stats = _optimize_with_progs(format_module, filename,
                                            image_format)
        stats.optimize_accounting(report_stats, total_bytes_in,
                                  total_bytes_out)
    except Exception as exc:
        print(exc)
        traceback.print_exc(exc)
        raise exc
