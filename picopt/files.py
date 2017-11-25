"""File utility operations."""
from __future__ import absolute_import, division, print_function

import os

from . import PROGRAM_NAME, stats
from .settings import Settings

REMOVE_EXT = '.{}-remove'.format(PROGRAM_NAME)


def replace_ext(filename, new_ext):
    """Replace the file extention."""
    filename_base = os.path.splitext(filename)[0]
    new_filename = '{}.{}'.format(filename_base, new_ext)
    return new_filename


def _cleanup_after_optimize_aux(filename, new_filename, old_format,
                                new_format):
    """
    Replace old file with better one or discard new wasteful file.
    """
    bytes_in = 0
    bytes_out = 0
    final_filename = filename
    try:
        bytes_in = os.stat(filename).st_size
        bytes_out = os.stat(new_filename).st_size
        if (bytes_out > 0) and ((bytes_out < bytes_in) or Settings.bigger):
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

        else:
            os.remove(new_filename)
            bytes_out = bytes_in
    except OSError as ex:
        print(ex)

    return final_filename, bytes_in, bytes_out


def cleanup_after_optimize(filename, new_filename, old_format, new_format):
    """
    Replace old file with better one or discard new wasteful file.

    And report results using the stats module.
    """
    final_filename, bytes_in, bytes_out = _cleanup_after_optimize_aux(
        filename, new_filename, old_format, new_format)
    return stats.ReportStats(final_filename, bytes_count=(bytes_in, bytes_out))
