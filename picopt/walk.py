"""Walk the directory trees and files and call the optimizers."""
import multiprocessing
import os
from multiprocessing.pool import AsyncResult
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple

from . import detect_format, optimize, stats, timestamp
from .formats.comic import Comic
from .settings import Settings
from .stats import ReportStats


def _comic_archive_skip(report_stats: Tuple[ReportStats]) -> ReportStats:
    return report_stats[0]


def walk_comic_archive(path: Path, image_format: str,
                       optimize_after: Optional[float]) \
                            -> AsyncResult: # noqa
    """
    Optimize a comic archive.

    This is done mostly inline to use the master processes process pool
    for workers. And to avoid calling back up into walk from a dedicated
    module or format processor. It does mean that we block on uncompress
    and on waiting for the contents subprocesses to compress.
    """
    # uncompress archive
    tmp_dir, report_stats = Comic.comic_archive_uncompress(path,
                                                           image_format)
    if tmp_dir is None:
        return Settings.pool.apply_async(_comic_archive_skip,
                                         args=(report_stats,))

    # optimize contents of archive
    archive_mtime = path.stat().st_mtime
    result_set = walk_dir(tmp_dir, optimize_after, True, archive_mtime)

    # wait for archive contents to optimize before recompressing
    nag_about_gifs = False
    for result in result_set:
        res = result.get()
        nag_about_gifs = nag_about_gifs or res.nag_about_gifs

    # recompress archive
    args = (path, image_format, Settings, nag_about_gifs)
    return Settings.pool.apply_async(Comic.comic_archive_compress,
                                     args=(args,))


def _is_skippable(full_path: Path) -> bool:
    """Handle things that are not optimizable files."""
    # File types
    if not Settings.follow_symlinks and full_path.is_symlink():
        if Settings.verbose > 1:
            print(full_path, 'is a symlink, skipping.')
        return True
    if full_path.name == timestamp.RECORD_FILENAME:
        return True
    if not full_path.exists():
        if Settings.verbose:
            print(full_path, 'was not found.')
        return True

    return False


def _is_older_than_timestamp(path: Path, walk_after: Optional[float],
                             archive_mtime: Optional[float]) -> bool:
    if walk_after is None:
        return False

    # if the file is in an archive, use the archive time if it
    # is newer. This helps if you have a new archive that you
    # collected from someone who put really old files in it that
    # should still be optimised
    mtime = timestamp.max_none((path.stat().st_mtime, archive_mtime))
    if mtime is None:
        return False
    return mtime <= walk_after


def walk_file(filename: Path, walk_after: Optional[float],
              recurse: Optional[int] = None,
              archive_mtime: Optional[float] = None) \
                      -> Set[AsyncResult]: # noqa
    """Optimize an individual file."""
    path = Path(filename)
    result_set: Set[AsyncResult] = set()
    if _is_skippable(path):
        return result_set

    walk_after = timestamp.get_walk_after(path, walk_after)

    # File is a directory
    if path.is_dir():
        return walk_dir(path, walk_after, recurse, archive_mtime)

    if _is_older_than_timestamp(path, walk_after, archive_mtime):
        return result_set

    # Check image format
    try:
        image_format = detect_format.detect_file(path)
    except Exception:
        res = Settings.pool.apply_async(stats.ReportStats,
                                        (path,),
                                        {'error': "Detect Format"})
        result_set.add(res)
        image_format = None

    if not image_format:
        return result_set

    if Settings.list_only:
        # list only
        print(f"{path}: {image_format}")
        return result_set

    if detect_format.is_format_selected(image_format, Comic.FORMATS,
                                        Comic.PROGRAMS):
        # comic archive
        result_set.add(walk_comic_archive(path, image_format, walk_after))
    else:
        # regular image
        args = [path, image_format, Settings]
        result_set.add(Settings.pool.apply_async(
                optimize.optimize_image, args=(args,)))
    return result_set


def walk_dir(dir_path: Path, walk_after: Optional[float],
             recurse: Optional[int] = None,
             archive_mtime: Optional[float] = None) \
                    -> Set[multiprocessing.pool.AsyncResult]: # noqa
    """Recursively optimize a directory."""
    if recurse is None:
        recurse = Settings.recurse

    result_set: Set[AsyncResult] = set()
    if not recurse:
        return result_set

    for root, _, filenames in os.walk(dir_path):
        root_path = Path(root)
        for filename in filenames:
            full_path = root_path.joinpath(filename)
            try:
                results = walk_file(full_path, walk_after, recurse,
                                    archive_mtime)
                result_set = result_set.union(results)
            except Exception:
                print(f"Error with file: {full_path}")
                raise

    return result_set


def _walk_all_files() -> Tuple[Set[Path], int, int, bool, List[Any]]:
    """
    Optimize the files from the arugments list in two batches.

    One for absolute paths which are probably outside the current
    working directory tree and one for relative files.
    """
    # Init records
    record_dirs: Set[Path] = set()
    result_set: Set[AsyncResult] = set()

    for filename in Settings.paths:
        # Record dirs to put timestamps in later
        full_path = Path(filename).resolve()
        if Settings.recurse and full_path.is_dir():
            record_dirs.add(full_path)

        walk_after = timestamp.get_walk_after(full_path)
        results = walk_file(full_path, walk_after, Settings.recurse)
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


def run() -> None:
    """Use preconfigured settings to optimize files."""
    # Setup Multiprocessing
    if Settings.jobs:
        Settings.pool.terminate()
        Settings.pool = multiprocessing.Pool(Settings.jobs)

    # Optimize Files
    record_dirs, bytes_in, bytes_out, nag_about_gifs, errors = \
        _walk_all_files()

    # Shut down multiprocessing
    Settings.pool.close()
    Settings.pool.join()

    # Write timestamps
    for filename in record_dirs:
        timestamp.record_timestamp(filename)

    # Finish by reporting totals
    stats.report_totals(bytes_in, bytes_out, nag_about_gifs, errors)
