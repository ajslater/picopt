"""File utility operations."""
from __future__ import print_function
import os

from . import stats
from . import name
from .settings import Settings

REMOVE_EXT = '.%s-remove' % name.PROGRAM_NAME

def replace_ext(filename, new_ext):
    """Replace the file extention."""
    filename_base = os.path.splitext(filename)[0]
    new_filename = '{}.{}'.format(filename_base, new_ext)
    return new_filename


def cleanup_after_optimize(filename, new_filename, old_format, new_format):
    """
    Replace old file with better one or discard new wasteful file.

    And report results.
    """
    bytes_diff = {'in': 0, 'out': 0}
    final_filename = filename
    try:
        filesize_in = os.stat(filename).st_size
        filesize_out = os.stat(new_filename).st_size
        bytes_diff['in'] = filesize_in
        bytes_diff['out'] = filesize_in  # overwritten on succes below
        if (filesize_out > 0) and ((filesize_out < filesize_in) or
                                   Settings.bigger):
            # old_format = detect_format.get_image_format(filename)
            if old_format != new_format:
                final_filename = replace_ext(filename,
                                             new_format.lower())
            rem_filename = filename + REMOVE_EXT
            if not Settings.test:
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

    return stats.ReportStats(final_filename, bytes_diff, [])
