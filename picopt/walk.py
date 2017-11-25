"""Walk the directory trees and files and call the optimizers."""
from __future__ import absolute_import, division, print_function

import multiprocessing
import os

from . import detect_format, optimize, stats, timestamp
from .formats import comic
from .settings import Settings


def _comic_archive_skip(report_stats):
    return report_stats


def walk_comic_archive(filename_full, image_format, optimize_after):
    """
    Optimize a comic archive.

    This is done mostly inline to use the master processes process pool
    for workers. And to avoid calling back up into walk from a dedicated
    module or format processor. It does mean that we block on uncompress
    and on waiting for the contents subprocesses to compress.
    """
    # uncompress archive
    tmp_dir, report_stats = comic.comic_archive_uncompress(filename_full,
                                                           image_format)
    if tmp_dir is None and report_stats:
        return Settings.pool.apply_async(_comic_archive_skip,
                                         args=report_stats)

    # optimize contents of archive
    archive_mtime = os.stat(filename_full).st_mtime
    result_set = walk_dir(tmp_dir, optimize_after, True, archive_mtime)

    # wait for archive contents to optimize before recompressing
    nag_about_gifs = False
    for result in result_set:
        res = result.get()
        nag_about_gifs = nag_about_gifs or res.nag_about_gifs

    # recompress archive
    args = (filename_full, image_format, Settings, nag_about_gifs)
    return Settings.pool.apply_async(comic.comic_archive_compress,
                                     args=(args,))


def _is_skippable(filename_full):
    """Handle things that are not optimizable files."""

    # File types
    if not Settings.follow_symlinks and os.path.islink(filename_full):
        return True
    elif os.path.basename(filename_full) == timestamp.RECORD_FILENAME:
        return True
    elif not os.path.exists(filename_full):
        if Settings.verbose:
            print(filename_full, 'was not found.')
        return True

    return False


def _is_older_than_timestamp(filename, walk_after, archive_mtime):
    if walk_after is None:
        return False

    mtime = os.stat(filename).st_mtime
    # if the file is in an archive, use the archive time if it
    # is newer. This helps if you have a new archive that you
    # collected from someone who put really old files in it that
    # should still be optimised
    if archive_mtime is not None:
        mtime = max(mtime, archive_mtime)
    return mtime <= walk_after


def walk_file(filename, walk_after, recurse=None, archive_mtime=None):
    """Optimize an individual file."""
    filename = os.path.normpath(filename)

    result_set = set()

    if _is_skippable(filename):
        return result_set

    walk_after = timestamp.get_walk_after(filename, walk_after)

    # File is a directory
    if os.path.isdir(filename):
        return walk_dir(filename, walk_after, recurse, archive_mtime)

    if _is_older_than_timestamp(filename, walk_after, archive_mtime):
        return result_set

    # Check image format
    image_format = detect_format.detect_file(filename)
    if not image_format:
        return result_set

    if Settings.list_only:
        # list only
        print("{}: {}".format(filename, image_format))
        return result_set

    if detect_format.is_format_selected(image_format, comic.FORMATS,
                                        comic.PROGRAMS):
        # comic archive
        result = walk_comic_archive(filename, image_format, walk_after)
    else:
        # regular image
        args = [filename, image_format, Settings]
        result = Settings.pool.apply_async(optimize.optimize_image,
                                           args=(args,))
    result_set.add(result)
    return result_set


def walk_dir(dir_path, walk_after, recurse=None, archive_mtime=None):
    """Recursively optimize a directory."""
    if recurse is None:
        recurse = Settings.recurse

    result_set = set()
    if not recurse:
        return result_set

    for root, _, filenames in os.walk(dir_path):
        for filename in filenames:
            filename_full = os.path.join(root, filename)
            try:
                results = walk_file(filename_full, walk_after, recurse,
                                    archive_mtime)
                result_set = result_set.union(results)
            except Exception:
                print("Error with file: {}".format(filename_full))
                raise

    return result_set


def _walk_all_files():
    """
    Optimize the files from the arugments list in two batches.

    One for absolute paths which are probably outside the current
    working directory tree and one for relative files.
    """
    # Init records
    record_dirs = set()
    result_set = set()

    for filename in Settings.paths:
        # Record dirs to put timestamps in later
        filename_full = os.path.abspath(filename)
        if Settings.recurse and os.path.isdir(filename_full):
            record_dirs.add(filename_full)

        walk_after = timestamp.get_walk_after(filename_full)
        results = walk_file(filename_full, walk_after, Settings.recurse)
        result_set = result_set.union(results)

    bytes_in = 0
    bytes_out = 0
    nag_about_gifs = False
    for result in result_set:
        res = result.get()
        bytes_in += res.bytes_in
        bytes_out += res.bytes_out
        nag_about_gifs = nag_about_gifs or res.nag_about_gifs

    return record_dirs, bytes_in, bytes_out, nag_about_gifs


def run():
    """Use preconfigured settings to optimize files."""
    # Setup Multiprocessing
    # manager = multiprocessing.Manager()
    Settings.pool = multiprocessing.Pool(Settings.jobs)

    # Optimize Files
    record_dirs, bytes_in, bytes_out, nag_about_gifs = _walk_all_files()

    # Shut down multiprocessing
    Settings.pool.close()
    Settings.pool.join()

    # Write timestamps
    for filename in record_dirs:
        timestamp.record_timestamp(filename)

    # Finish by reporting totals
    stats.report_totals(bytes_in, bytes_out, nag_about_gifs)
