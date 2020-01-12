"""Walk the directory trees and files and call the optimizers."""
import multiprocessing
import os
import time

from multiprocessing.pool import AsyncResult
from multiprocessing.pool import Pool
from pathlib import Path
from typing import Any
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

from . import detect_format
from . import optimize
from . import stats
from . import timestamp
from .formats.comic import Comic
from .settings import Settings
from .stats import ReportStats
from .timestamp import Timestamp


def _comic_archive_skip(report_stats: Tuple[ReportStats]) -> ReportStats:
    return report_stats[0]


def walk_comic_archive(
    settings: Settings,
    pool: Pool,
    tso: Timestamp,
    path: Path,
    image_format: str,
    optimize_after: Optional[float],
) -> AsyncResult:
    """
    Optimize a comic archive.

    This is done mostly inline to use the master processes process pool
    for workers. And to avoid calling back up into walk from a dedicated
    module or format processor. It does mean that we block on uncompress
    and on waiting for the contents subprocesses to compress.
    """
    # uncompress archive
    tmp_dir, report_stats = Comic.comic_archive_uncompress(settings, path, image_format)
    if tmp_dir is None:
        return pool.apply_async(_comic_archive_skip, args=(report_stats,))

    # optimize contents of archive
    archive_mtime = path.stat().st_mtime
    result_set = walk_dir(
        settings, pool, tso, tmp_dir, optimize_after, True, archive_mtime
    )

    # wait for archive contents to optimize before recompressing
    nag_about_gifs = False
    for result in result_set:
        res = result.get()
        nag_about_gifs = nag_about_gifs or res.nag_about_gifs

    # recompress archive
    args = (path, image_format, settings, nag_about_gifs)
    return pool.apply_async(Comic.comic_archive_compress, args=(args,))


def _is_skippable(settings: Settings, full_path: Path) -> bool:
    """Handle things that are not optimizable files."""
    # File types
    if not settings.follow_symlinks and full_path.is_symlink():
        if settings.verbose > 1:
            print(full_path, "is a symlink, skipping.")
        return True
    if full_path.name == timestamp.RECORD_FILENAME:
        return True
    if not full_path.exists():
        if settings.verbose:
            print(full_path, "was not found.")
        return True

    return False


def _is_older_than_timestamp(
    path: Path, walk_after: Optional[float], archive_mtime: Optional[float]
) -> bool:
    if walk_after is None:
        return False

    # if the file is in an archive, use the archive time if it
    # is newer. This helps if you have a new archive that you
    # collected from someone who put really old files in it that
    # should still be optimised
    mtime = Timestamp.max_none((path.stat().st_mtime, archive_mtime))
    if mtime is None:
        return False
    return mtime <= walk_after


def walk_file(
    settings: Settings,
    pool: Pool,
    tso: timestamp.Timestamp,
    filename: Path,
    walk_after: Optional[float],
    recurse: Optional[int] = None,
    archive_mtime: Optional[float] = None,
) -> Set[AsyncResult]:
    """Optimize an individual file."""
    path = Path(filename)
    result_set: Set[AsyncResult] = set()
    if _is_skippable(settings, path):
        return result_set

    walk_after = tso.get_walk_after(path, walk_after)

    # File is a directory
    if path.is_dir():
        return walk_dir(settings, pool, tso, path, walk_after, recurse, archive_mtime)

    if _is_older_than_timestamp(path, walk_after, archive_mtime):
        return result_set

    # Check image format
    #    try:
    image_format = detect_format.detect_file(settings, path)
    #    except Exception:
    #        res = settings.pool.apply_async(
    #            stats.ReportStats, (path,), {"error": "Detect Format"}
    #        )
    #        result_set.add(res)
    #        image_format = None

    if not image_format:
        return result_set

    if settings.list_only:
        # list only
        print(f"{path}: {image_format}")
        return result_set

    if detect_format.is_format_selected(
        settings, image_format, Comic.FORMATS, Comic.PROGRAMS
    ):
        # comic archive
        result_set.add(
            walk_comic_archive(settings, pool, tso, path, image_format, walk_after)
        )
    else:
        # regular image
        args = [path, image_format, settings]
        result_set.add(pool.apply_async(optimize.optimize_image, args=(args,)))
    return result_set


def walk_dir(
    settings: Settings,
    pool: Pool,
    tso: Timestamp,
    dir_path: Path,
    walk_after: Optional[float],
    recurse: Optional[int] = None,
    archive_mtime: Optional[float] = None,
) -> Set[multiprocessing.pool.AsyncResult]:
    """Recursively optimize a directory."""
    if recurse is None:
        recurse = settings.recurse

    result_set: Set[AsyncResult] = set()
    if not recurse:
        return result_set

    for root, _, filenames in os.walk(dir_path):
        root_path = Path(root)
        for filename in filenames:
            full_path = root_path / filename
            try:
                results = walk_file(
                    settings, pool, tso, full_path, walk_after, recurse, archive_mtime
                )
                result_set = result_set.union(results)
            except Exception:
                print(f"Error with file: {full_path}")
                raise

    return result_set


def _walk_all_files(
    settings: Settings, pool: Pool, tso: Timestamp
) -> Tuple[Set[Path], int, int, bool, List[Any]]:
    """
    Optimize the files from the arugments list in two batches.

    One for absolute paths which are probably outside the current
    working directory tree and one for relative files.
    """
    # Init records
    record_dirs: Set[Path] = set()
    result_set: Set[AsyncResult] = set()

    for filename in settings.paths:
        path = Path(filename)
        # Record dirs to put timestamps in later
        if settings.recurse and path.is_dir():
            record_dirs.add(path)

        walk_after = tso.get_walk_after(path)
        results = walk_file(settings, pool, tso, path, walk_after, settings.recurse)
        result_set = result_set.union(results)

    bytes_in = 0
    bytes_out = 0
    nag_about_gifs = False
    errors: List[Tuple[Path, str]] = []
    for result in result_set:
        res = result.get()
        if res.error:
            errors += [(res.final_path, res.error)]
            continue
        bytes_in += res.bytes_in
        bytes_out += res.bytes_out
        nag_about_gifs = nag_about_gifs or res.nag_about_gifs

    return record_dirs, bytes_in, bytes_out, nag_about_gifs, errors


def run(settings: Settings) -> bool:
    """Use preconfigured settings to optimize files."""
    if not settings.can_do:
        print("All optimizers are not available or disabled.")
        return False

    if settings.optimize_after is not None and settings.verbose:
        print("Optimizing after", time.ctime(settings.optimize_after))

    # Setup Multiprocessing
    pool = Pool(settings.jobs)
    tso = Timestamp(settings)

    # Optimize Files
    record_dirs, bytes_in, bytes_out, nag_about_gifs, errors = _walk_all_files(
        settings, pool, tso
    )

    # Shut down multiprocessing
    pool.close()
    pool.join()

    # Write timestamps
    for filename in record_dirs:
        tso.record_timestamp(filename)

    # Finish by reporting totals
    stats.report_totals(settings, bytes_in, bytes_out, nag_about_gifs, errors)
    return True
