"""File utility operations."""
from pathlib import Path
from typing import Tuple

from . import stats
from .settings import Settings
from .stats import ReportStats


def _cleanup_after_optimize_aux(
    settings: Settings, old_path: Path, new_path: Path, old_format: str, new_format: str
) -> Tuple[Path, int, int]:
    """Replace old file with better one or discard new wasteful file."""
    bytes_in = 0
    bytes_out = 0
    final_path = old_path
    try:
        bytes_in = old_path.stat().st_size
        bytes_out = new_path.stat().st_size
        if not settings.test and (
            (bytes_out > 0) and ((bytes_out < bytes_in) or settings.bigger)
        ):
            if old_format != new_format:
                final_path = old_path.with_suffix("." + new_format.lower())
            new_path.replace(final_path)
            if final_path != old_path:
                old_path.unlink()
        else:
            new_path.unlink()
            bytes_out = bytes_in
    except OSError as ex:
        print(ex)

    return final_path, bytes_in, bytes_out


def cleanup_after_optimize(
    settings: Settings, old_path: Path, new_path: Path, old_format: str, new_format: str
) -> ReportStats:
    """
    Replace old file with better one or discard new wasteful file.

    And report results using the stats module.
    """
    final_path, bytes_in, bytes_out = _cleanup_after_optimize_aux(
        settings, old_path, new_path, old_format, new_format
    )
    return stats.ReportStats(final_path, bytes_count=(bytes_in, bytes_out))
