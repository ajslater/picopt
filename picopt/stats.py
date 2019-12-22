"""Statistics for the optimization operations."""
from pathlib import Path
from typing import List, Optional, Tuple

from .settings import Settings

ABBREVS = (
    (1 << int(50), 'PiB'),
    (1 << int(40), 'TiB'),
    (1 << int(30), 'GiB'),
    (1 << int(20), 'MiB'),
    (1 << int(10), 'kiB'),
    (1, 'bytes')
)


class ReportStats(object):
    """Container for reported stats from optimization operations."""

    def __init__(self, final_path: Path, report: Optional[str] = None,
                 bytes_count: Optional[Tuple[int, int]] = None,
                 nag_about_gifs: bool = False,
                 error: Optional[str] = None):
        """Initialize required instance variables."""
        self.final_path = final_path
        self.report_list = []
        self.error = error
        if report:
            self.report_list.append(report)
        if bytes_count:
            self.bytes_in = bytes_count[0]
            self.bytes_out = bytes_count[1]
        else:
            self.bytes_count = 0
            self.bytes_count = 0

        self.nag_about_gifs = nag_about_gifs


def _humanize_bytes(num_bytes: int, precision: int = 1) -> str:
    """
    Return a humanized string representation of a number of num_bytes.

    from:
    http://code.activestate.com/recipes/
           577081-humanized-representation-of-a-number-of-num_bytes/

    Assumes python 3 style division.

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
            factored_bytes = int(num_bytes / factor)
            factor_suffix = suffix
            break

    if factored_bytes == 1:
        precision = 0

    return '{:.{prec}f} {}'.format(factored_bytes, factor_suffix,
                                   prec=precision)


def new_percent_saved(report_stats: ReportStats) -> str:
    """Spit out how much space the optimization saved."""
    size_in = report_stats.bytes_in
    if size_in > 0:
        size_out = report_stats.bytes_out
        ratio = size_out / size_in
        kb_saved = _humanize_bytes(size_in - size_out)
    else:
        ratio = 0
        kb_saved = f'0 {ABBREVS[-1]}'
    percent_saved = (1 - ratio) * 100

    result = '{:.{prec}f}% ({})'.format(percent_saved, kb_saved, prec=2)
    return result


def report_saved(report_stats: ReportStats) -> None:
    """Record the percent saved & print it."""
    if Settings.verbose:
        report = ''
        path = report_stats.final_path

        report += f'{path}: '
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


def report_totals(bytes_in: int, bytes_out: int, nag_about_gifs: bool,
                  errors: List[str]) -> None:
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
        msg += " a total of {} or {:.{prec}f}%".format(
            _humanize_bytes(bytes_saved), percent_bytes_saved, prec=2)
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

    if not errors:
        return

    print("Errors with the following files:")
    for error in errors:
        print(f"{error[0]}: {error[1]}")


def skip(type_name: str, path: Path) -> ReportStats:
    """Provide reporting statistics for a skipped file."""
    report = f'Skipping {type_name} file: {path}'
    report_stats = ReportStats(path, report=report)
    return report_stats
