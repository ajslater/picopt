"""Timestamp writer for keeping track of bulk optimizations."""
from __future__ import absolute_import, division, print_function

import os
from datetime import datetime

from . import PROGRAM_NAME
from .settings import Settings

RECORD_FILENAME = '.{}_timestamp'.format(PROGRAM_NAME)
TIMESTAMP_CACHE = {}
OLD_TIMESTAMPS = set()


def _get_timestamp(dirname_full, remove):
    """
    Get the timestamp from the timestamp file.

    Optionally mark it for removal if we're going to write another one.
    """
    if dirname_full not in TIMESTAMP_CACHE:
        record_filename = os.path.join(dirname_full, RECORD_FILENAME)

        if os.path.exists(record_filename):
            mtime = os.stat(record_filename).st_mtime
            mtime_str = datetime.fromtimestamp(mtime)
            print('Found timestamp {}:{}'.format(dirname_full, mtime_str))
            if Settings.record_timestamp and remove:
                OLD_TIMESTAMPS.add(record_filename)
        else:
            mtime = None

        TIMESTAMP_CACHE[dirname_full] = mtime
    return TIMESTAMP_CACHE[dirname_full]


def _get_parent_timestamp(dirname, mtime):
    """
    Get the timestamps up the directory tree.

    Because they affect every subdirectory.
    """
    parent_pathname = os.path.dirname(dirname)

    mtime = max(_get_timestamp(parent_pathname, False), mtime)

    if dirname != os.path.dirname(parent_pathname):
        mtime = _get_parent_timestamp(parent_pathname, mtime)

    return mtime


def get_walk_after(filename, optimize_after=None):
    """
    Figure out the which mtime to check against.

    If we have to look up the path return that.
    """
    if Settings.optimize_after is not None:
        return Settings.optimize_after

    dirname = os.path.dirname(filename)
    if optimize_after is None:
        optimize_after = _get_parent_timestamp(dirname, optimize_after)
    got_timestamp = _get_timestamp(dirname, True)
    optimize_after = max(got_timestamp, optimize_after)

    return optimize_after


def record_timestamp(pathname_full):
    """Record the timestamp of running in a dotfile."""
    if Settings.test or Settings.list_only or not Settings.record_timestamp:
        return
    elif not Settings.follow_symlinks and os.path.islink(pathname_full):
        if Settings.verbose:
            print('Not setting timestamp because not following symlinks')
        return
    elif not os.path.isdir(pathname_full):
        if Settings.verbose:
            print('Not setting timestamp for a non-directory')
        return

    record_filename_full = os.path.join(pathname_full, RECORD_FILENAME)
    try:
        with open(record_filename_full, 'w'):
            os.utime(record_filename_full, None)
        if Settings.verbose:
            print("Set timestamp: {}".format(record_filename_full))
        for fname in OLD_TIMESTAMPS:
            if fname.startswith(pathname_full) and \
               fname != record_filename_full:
                # only remove timestamps below the curent path
                # but don't remove the timestamp we just set!
                os.remove(fname)
                if Settings.verbose:
                    print('Removed old timestamp: {}'.format(fname))
    except IOError:
        print("Could not set timestamp in {}".format(pathname_full))
