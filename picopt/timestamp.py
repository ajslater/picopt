"""Timestamp writer for keeping track of bulk optimizations."""
from __future__ import absolute_import, division, print_function

import os
import sys
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
    record_filename = os.path.join(dirname_full, RECORD_FILENAME)

    if not os.path.exists(record_filename):
        return None

    mtime = os.stat(record_filename).st_mtime
    mtime_str = datetime.fromtimestamp(mtime)
    print('Found timestamp {}:{}'.format(dirname_full, mtime_str))
    if Settings.record_timestamp and remove:
        OLD_TIMESTAMPS.add(record_filename)
    return mtime


def _get_timestamp_cached(dirname_full, remove):
    """
    Get the timestamp from the cache or fill the cache
    Much quicker than reading the same files over and over
    """
    if dirname_full not in TIMESTAMP_CACHE:
        mtime = _get_timestamp(dirname_full, remove)
        TIMESTAMP_CACHE[dirname_full] = mtime
    return TIMESTAMP_CACHE[dirname_full]


if sys.version > '3':
    def max_none(lst):
        """Max function that works in python 3."""
        return max((x for x in lst if x is not None), default=None)
else:
    def max_none(lst):
        """Max function from python 2."""
        return max(lst)


def _max_timestamps(dirname_full, remove, compare_tstamp):
    """Compare a timestamp file to one passed in. Get the max."""
    tstamp = _get_timestamp_cached(dirname_full, remove)
    return max_none((tstamp, compare_tstamp))


def _get_parent_timestamp(dirname, mtime):
    """
    Get the timestamps up the directory tree. All the way to root.

    Because they affect every subdirectory.
    """
    parent_pathname = os.path.dirname(dirname)

    # max between the parent timestamp the one passed in
    mtime = _max_timestamps(parent_pathname, False, mtime)

    if dirname != os.path.dirname(parent_pathname):
        # this is only called if we're not at the root
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
    return _max_timestamps(dirname, True, optimize_after)


def record_timestamp(pathname_full):
    """Record the timestamp of running in a dotfile."""
    if Settings.test or Settings.list_only or not Settings.record_timestamp:
        return
    if not Settings.follow_symlinks and os.path.islink(pathname_full):
        if Settings.verbose:
            print('Not setting timestamp because not following symlinks')
        return
    if not os.path.isdir(pathname_full):
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
