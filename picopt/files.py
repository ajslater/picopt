"""File utility operations."""
from pathlib import Path

from . import PROGRAM_NAME, stats
from .settings import Settings

REMOVE_EXT = f'.{PROGRAM_NAME}-remove'


def _cleanup_after_optimize_aux(filename, new_filename, old_format,
                                new_format):
    """
    Replace old file with better one or discard new wasteful file.
    """
    bytes_in = 0
    bytes_out = 0
    file_path = Path(filename)
    final_path = file_path
    try:
        new_path = Path(new_filename)
        bytes_in = file_path.stat().st_size
        bytes_out = new_path.stat().st_size
        if (bytes_out > 0) and ((bytes_out < bytes_in) or Settings.bigger):
            if old_format != new_format:
                final_path = file_path.with_suffix('.'+new_format.lower())
            if not Settings.test:
                new_path.replace(final_path)
            else:
                new_path.unlink()
        else:
            new_path.unlink()
            bytes_out = bytes_in
    except OSError as ex:
        print(ex)

    return final_path, bytes_in, bytes_out


def cleanup_after_optimize(filename, new_filename, old_format, new_format):
    """
    Replace old file with better one or discard new wasteful file.

    And report results using the stats module.
    """
    final_filename, bytes_in, bytes_out = _cleanup_after_optimize_aux(
        filename, new_filename, old_format, new_format)
    return stats.ReportStats(final_filename, bytes_count=(bytes_in, bytes_out))
