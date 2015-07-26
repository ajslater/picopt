import os
import optimize
import name

RECORD_FILENAME = '.%s_timestamp' % name.PROGRAM_NAME


def get_timestamp(dirname_full, remove, arguments):
    """ get the timestamp from the timestamp file and optionally remove it
        if we're going to write another one.
    """
    record_filename = os.path.join(dirname_full, RECORD_FILENAME)

    if os.path.exists(record_filename):
        mtime = os.stat(record_filename).st_mtime
        if arguments.record_timestamp and remove:
            os.remove(record_filename)
        return mtime

    return None


def get_parent_timestamp(full_pathname, mtime, arguments):
    """ get the timestamps up the directory tree because they affect
        every subdirectory """
    parent_pathname = os.path.dirname(full_pathname)

    mtime = max(get_timestamp(parent_pathname, False, arguments), mtime)

    if parent_pathname == os.path.dirname(parent_pathname):
        return mtime

    return get_parent_timestamp(parent_pathname, mtime, arguments)


def get_optimize_after(current_path, look_up, optimize_after, arguments):
    """ Figure out the which mtime to check against and if we look up
        return that we've looked up too"""
    if arguments.optimize_after is not None:
        optimize_after = arguments.optimize_after
    else:
        if look_up:
            optimize_after = get_parent_timestamp(current_path,
                                                  optimize_after,
                                                  arguments)
        optimize_after = max(get_timestamp(current_path, True, arguments),
                             optimize_after)
    return optimize_after


def optimize_files_after(path, arguments, file_list, multiproc):
    """ compute the optimize after date for the a batch of files
        and then optimize them.
    """
    optimize_after = get_optimize_after(path, True, None, arguments)
    return optimize.optimize_files(path, file_list, arguments, multiproc,
                                   optimize_after)


def record_timestamp(pathname_full, arguments):
    """Record the timestamp of running in a dotfile"""
    if arguments.test or arguments.list_only or not arguments.record_timestamp:
        return
    elif not arguments.follow_symlinks and os.path.islink(pathname_full):
        if arguments.verbose:
            print('Not setting timestamp because not following symlinks')
        return
    elif not os.path.isdir(pathname_full):
        if arguments.verbose:
            print('Not setting timestamp for a non-directory')
        return

    record_filename_full = os.path.join(pathname_full, RECORD_FILENAME)
    try:
        with open(record_filename_full, 'w'):
            os.utime(record_filename_full, None)
        if arguments.verbose:
            print("Set timestamp: %s" % record_filename_full)
    except IOError:
        print("Could not set timestamp in %s" % pathname_full)
