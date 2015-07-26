from collections import namedtuple
import os
import shutil
import traceback

import detect_format
import gif
import jpeg
import name
import png
import stats


REMOVE_EXT = '.%s-remove' % name.PROGRAM_NAME
NEW_EXT = '.%s-optimized.png' % name.PROGRAM_NAME


ExtArgs = namedtuple('ExtArgs', ['old_filename', 'new_filename', 'arguments'])


def replace_ext(filename, new_ext):
    """replaces the file extention"""
    filename_base = os.path.splitext(filename)[0]
    new_filename = '{}.{}'.format(filename_base, new_ext)
    return new_filename


def cleanup_after_optimize(filename, new_filename, arguments):
    """report results. replace old file with better one or discard new wasteful
       file"""

    bytes_diff = {'in': 0, 'out': 0}
    final_filename = filename
    try:
        filesize_in = os.stat(filename).st_size
        filesize_out = os.stat(new_filename).st_size
        bytes_diff['in'] = filesize_in
        bytes_diff['out'] = filesize_in  # overwritten on succes below
        if (filesize_out > 0) and ((filesize_out < filesize_in) or
                                   arguments.bigger):
            old_image_format = detect_format.get_image_format(filename,
                                                              arguments)
            new_image_format = detect_format.get_image_format(new_filename,
                                                              arguments)
            if old_image_format != new_image_format:
                final_filename = replace_ext(filename,
                                             new_image_format.lower())
            rem_filename = filename + REMOVE_EXT
            if not arguments.test:
                os.rename(filename, rem_filename)
                os.rename(new_filename, final_filename)
                os.remove(rem_filename)
            else:
                os.remove(new_filename)

            bytes_diff['out'] = filesize_out  # only on completion
        else:
            os.remove(new_filename)
    except OSError as ex:
        print(ex)

    return stats.ReportStats._make([final_filename, bytes_diff, []])


def optimize_image_external(filename, arguments, func):
    """this could be a decorator"""
    new_filename = os.path.normpath(filename + NEW_EXT)
    shutil.copy2(filename, new_filename)

    ext_args = ExtArgs._make([filename, new_filename, arguments])
    func(ext_args)

    report_stats = cleanup_after_optimize(filename, new_filename, arguments)
    percent = stats.new_percent_saved(report_stats)
    if percent != 0:
        report = '%s: %s' % (func.__name__, percent)
    else:
        report = ''
    report_stats.report_list.append(report)

    return report_stats


def optimize_with_progs(funcs, filename, type_name, best_only,
                        arguments):
    """ Use either all the optimizing functions in sequence or just the
        best one to optimize the image and report back statistics """
    filesize_in = os.stat(filename).st_size
    report_stats = None

    for func in funcs:
        if not getattr(arguments, func.__name__):
            continue
        report_stats = optimize_image_external(filename,
                                               arguments,
                                               func)
        filename = report_stats.final_filename
        if best_only:
            break

    if report_stats is not None:
        report_stats.bytes_diff['in'] = filesize_in
    else:
        report_stats = stats.skip(type_name, filename)

    return report_stats


def optimize_image(arg):
    """optimizes a given image from a filename"""
    try:
        filename, image_format, arguments, total_bytes_in, total_bytes_out, \
            nag_about_gifs = arg

        if detect_format.is_format_selected(image_format,
                                            arguments.to_png_formats,
                                            arguments, arguments.optipng or
                                            arguments.pngout):
            report_stats = png.optimize(filename, arguments)
        elif detect_format.is_format_selected(image_format, jpeg.FORMATS,
                                              arguments,
                                              arguments.mozjpeg or
                                              arguments.jpegrescan or
                                              arguments.jpegtran):
            report_stats = jpeg.optimize(filename, arguments)
        elif detect_format.is_format_selected(image_format, gif.FORMATS,
                                              arguments, arguments.gifsicle):
            # this captures still GIFs too if not caught above
            report_stats = gif.optimize(filename, arguments)
            nag_about_gifs.set(True)
        else:
            if arguments.verbose > 1:
                print(filename, image_format)  # image.mode)
                print("\tFile format not selected.")
            return

        stats.optimize_accounting(report_stats, total_bytes_in,
                                  total_bytes_out, arguments)
    except Exception as exc:
        print(exc)
        traceback.print_exc(exc)
        raise exc
