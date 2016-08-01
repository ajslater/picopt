"""Statistics for the optimization operations."""
from __future__ import division
from __future__ import print_function
from collections import namedtuple
import os
import sys

from .settings import Settings


if sys.version > '3':
    LongInt = int
else:
    LongInt = long


ABBREVS = (
    (1 << LongInt(50), 'PiB'),
    (1 << LongInt(40), 'TiB'),
    (1 << LongInt(30), 'GiB'),
    (1 << LongInt(20), 'MiB'),
    (1 << LongInt(10), 'kiB'),
    (1, 'bytes')
)


ReportStats = namedtuple('ReportStats', ['final_filename', 'bytes_diff',
                                         'report_list'])


def humanize_bytes(num_bytes, precision=1):
    """
    Return a humanized string representation of a number of num_bytes.

    from:
    http://code.activestate.com/recipes/
           577081-humanized-representation-of-a-number-of-num_bytes/

    Assumes `from __future__ import division`.

    >>> humanize_bytes(1)
    '1 byte'
    >>> humanize_bytes(1024)
    '1.0 kB'
    >>> humanize_bytes(1024*123)
    '123.0 kB'
    >>> humanize_bytes(1024*12342)
    '12.1 MB'
    >>> humanize_bytes(1024*12342,2)
    '12.05 MB'
    >>> humanize_bytes(1024*1234,2)
    '1.21 MB'
    >>> humanize_bytes(1024*1234*1111,2)
    '1.31 GB'
    >>> humanize_bytes(1024*1234*1111,1)
    '1.3 GB'
    """
    if num_bytes == 0:
        return 'no bytes'
    if num_bytes == 1:
        return '1 byte'

    factored_bytes = 0
    factor_suffix = 'bytes'
    for factor, suffix in ABBREVS:
        if num_bytes >= factor:
            factored_bytes = num_bytes / factor
            factor_suffix = suffix
            break

    if factored_bytes == 1:
        precision = 0

    return '%.*f %s' % (precision, factored_bytes, factor_suffix)


def new_percent_saved(report_stats):
    """Spit out how much space the optimization saved."""
    size_in = report_stats.bytes_diff['in']
    if size_in != 0:
        size_out = report_stats.bytes_diff['out']
        ratio = size_out / size_in
    else:
        ratio = 0
    percent_saved = (1 - ratio) * 100

    size_saved_kb = humanize_bytes(size_in - size_out)
    result = '%.*f%s (%s)' % (2, percent_saved, '%', size_saved_kb)
    return result


def truncate_cwd(full_filename):
    """Remove the cwd from the full filename."""
    truncated_filename = full_filename.split(Settings.dir, 1)[1]
    truncated_filename = truncated_filename.split(os.sep, 1)[1]
    return truncated_filename


def optimize_accounting(report_stats, total_bytes_in, total_bytes_out):
    """Record the percent saved, print it and add it to the totals."""
    if Settings.verbose:
        report = ''
#        if Settings.archive_name is not None:
#            truncated_filename = report_stats.final_filename.split(
#                ARCHIVE_TMP_DIR_PREFIX, 1)[1]
#            truncated_filename = truncated_filename.split(os.sep, 1)[1]
#            report += '  %s: ' % Settings.archive_name
        if Settings.dir in report_stats.final_filename:
            truncated_filename = truncate_cwd(report_stats.final_filename)
        else:
            truncated_filename = report_stats.final_filename

        report += '%s: ' % truncated_filename
        total = new_percent_saved(report_stats)
        if total:
            report += total
        else:
            report += '0%'
        if Settings.test:
            report += ' could be saved.'
        if Settings.verbose > 1:
            tools_report = ', '.join(report_stats.report_list)
            if tools_report:
                report += '\n\t' + tools_report
        print(report)

    total_bytes_in.set(total_bytes_in.get() + report_stats.bytes_diff['in'])
    total_bytes_out.set(total_bytes_out.get() + report_stats.bytes_diff['out'])


def report_totals(bytes_in, bytes_out, nag_about_gifs):
    """Report the total number and percent of bytes saved."""
    if bytes_in:
        bytes_saved = bytes_in - bytes_out
        percent_bytes_saved = bytes_saved / bytes_in * 100
        msg = ''
        if Settings.test:
            if percent_bytes_saved > 0:
                msg += "Could save"
            elif percent_bytes_saved == 0:
                msg += "Could even out for"
            else:
                msg += "Could lose"
        else:
            if percent_bytes_saved > 0:
                msg += "Saved"
            elif percent_bytes_saved == 0:
                msg += "Evened out"
            else:
                msg = "Lost"
        msg += " a total of %s or %.*f%s" % (humanize_bytes(bytes_saved),
                                             2, percent_bytes_saved, '%')
        if Settings.verbose:
            print(msg)
            if Settings.test:
                print("Test run did not change any files.")

    else:
        if Settings.verbose:
            print("Didn't optimize any files.")

    if nag_about_gifs and Settings.verbose:
        print("Most animated GIFS would be better off converted to"
              " HTML5 video")


def skip(type_name, filename):
    """Provide reporting statistics for a skipped file."""
    bytes_diff = {'in': 0, 'out': 0}
    rep = ['Skipping %s file: %s' % (type_name, filename)]
    report_stats = ReportStats._make([filename, bytes_diff, [rep]])
    return report_stats
