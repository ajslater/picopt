"""Walk the directory trees and files and call the optimizers."""
from __future__ import print_function
import os
import multiprocessing

import comic
import detect_format
import optimize
import stats
import timestamp
from .settings import Settings


def process_if_not_file(filename_full, multiproc, walk_after, recurse,
                        archive_mtime):
    """Handle things that are not optimizable files."""
    result_set = set()

    # File types
    if not Settings.follow_symlinks and os.path.islink(filename_full):
        return result_set
    elif os.path.basename(filename_full) == timestamp.RECORD_FILENAME:
        return result_set
    elif os.path.isdir(filename_full):
        results = walk_dir(filename_full, multiproc,
                           walk_after, recurse, archive_mtime)
        result_set = result_set.union(results)
        return result_set
    elif not os.path.exists(filename_full):
        if Settings.verbose:
            print(filename_full, 'was not found.')
        return result_set

    # Timestamp
    if walk_after is not None:
        mtime = os.stat(filename_full).st_mtime
        # if the file is in an archive, use the archive time if it
        # is newer. This helps if you have a new archive that you
        # collected from someone who put really old files in it that
        # should still be optimised
        if archive_mtime is not None:
            mtime = max(mtime, archive_mtime)
        if mtime <= walk_after:
            return result_set

    return None


def walk_file(filename_full, multiproc, walk_after, recurse=None,
              archive_mtime=None):
    """Optimize an individual file."""
    filename_full = os.path.normpath(filename_full)

    result_set = process_if_not_file(
        filename_full, multiproc, walk_after, recurse, archive_mtime)
    if result_set is not None:
        return result_set
    result_set = set()

    # Image format
    image_format = detect_format.detect_file(filename_full)
    if not image_format:
        return result_set

    if Settings.list_only:
        # list only
        print("%s : %s" % (filename_full, image_format))
        return result_set

    if detect_format.is_format_selected(image_format, comic.FORMATS,
                                        comic.PROGRAMS):
        # comic archive
        result = comic.walk_comic_archive(filename_full, image_format,
                                          multiproc, walk_after)
    else:
        # regular image
        args = [filename_full, image_format, Settings,
                multiproc['in'], multiproc['out'], multiproc['nag_about_gifs']]
        result = multiproc['pool'].apply_async(optimize.optimize_image,
                                               args=(args,))
    result_set.add(result)
    return result_set


def walk_dir(dir_path, multiproc, walk_after, recurse=None,
             archive_mtime=None):
    """Recursively optimize a directory."""
    if recurse is None:
        recurse = Settings.recurse

    result_set = set()
    if not recurse:
        return result_set

    filenames = os.listdir(dir_path)
    filenames.sort()
    walk_after = timestamp.get_walk_after(dir_path, walk_after)

    for filename in filenames:
        filename_full = os.path.join(dir_path, filename)
        results = walk_file(filename_full, multiproc, walk_after, recurse,
                            archive_mtime)
        result_set = result_set.union(results)
    return result_set


def walk_all_files(multiproc):
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
        results = walk_file(filename_full, multiproc, Settings.recurse,
                            walk_after)
        result_set = result_set.union(results)

    for result in result_set:
        result.wait()

    return record_dirs


def run():
    """Use preconfigured settings to optimize files."""
    # Setup Multiprocessing
    manager = multiprocessing.Manager()
    total_bytes_in = manager.Value(int, 0)
    total_bytes_out = manager.Value(int, 0)
    nag_about_gifs = manager.Value(bool, False)
    pool = multiprocessing.Pool(Settings.jobs)

    multiproc = {'pool': pool, 'in': total_bytes_in, 'out': total_bytes_out,
                 'nag_about_gifs': nag_about_gifs}

    # Optimize Files
    record_dirs = walk_all_files(multiproc)

    # Shut down multiprocessing
    pool.close()
    pool.join()

    # Write timestamps
    for filename in record_dirs:
        timestamp.record_timestamp(filename)

    # Finish by reporting totals
    stats.report_totals(multiproc['in'].get(), multiproc['out'].get(),
                        multiproc['nag_about_gifs'].get())
