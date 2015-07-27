from __future__ import print_function
import os

import comic
import detect_format
import optimize_image
import timestamp


def optimize_file(filename_full, arguments, multiproc, optimize_after):
    """ Optimize an individual file """
    if optimize_after is not None:
        mtime = os.stat(filename_full).st_mtime
        if mtime <= optimize_after:
            return

    image_format = detect_format.detect_file(filename_full, arguments)
    if not image_format:
        return

    if arguments.list_only:
        # list only
        print("%s : %s" % (filename_full, image_format))
    elif detect_format.is_format_selected(image_format, comic.FORMATS,
                                          comic.PROGRAMS, arguments):
        return comic.optimize_comic_archive(filename_full, image_format,
                                            arguments, multiproc,
                                            optimize_after)
    else:
        # regular image
        args = [filename_full, image_format, arguments,
                multiproc['in'], multiproc['out'], multiproc['nag_about_gifs']]
        return multiproc['pool'].apply_async(optimize_image.optimize_image,
                                             args=(args,))


def optimize_dir(filename_full, arguments, multiproc, optimize_after):
    """ Recursively optimize a directory """
    if not arguments.recurse:
        return set()
    next_dir_list = os.listdir(filename_full)
    next_dir_list.sort()
    optimize_after = timestamp.get_optimize_after(filename_full, False,
                                                  optimize_after, arguments)
    return optimize_files(filename_full, next_dir_list, arguments,
                          multiproc, optimize_after)


def optimize_files(cwd, filter_list, arguments, multiproc, optimize_after):
    """sorts through a list of files, decends directories and
       calls the optimizer on the extant files"""

    result_set = set()
    for filename in filter_list:

        filename_full = os.path.join(cwd, filename)
        filename_full = os.path.normpath(filename_full)

        if not arguments.follow_symlinks and os.path.islink(filename_full):
            continue
        elif os.path.basename(filename_full) == timestamp.RECORD_FILENAME:
            continue
        elif os.path.isdir(filename_full):
            results = optimize_dir(filename_full, arguments, multiproc,
                                   optimize_after)
            result_set = result_set.union(results)
        elif os.path.exists(filename_full):
            result = optimize_file(filename_full, arguments, multiproc,
                                   optimize_after)
            if result:
                result_set.add(result)
        elif arguments.verbose:
            print(filename_full, 'was not found.')
    return result_set


def optimize_files_after(path, arguments, file_list, multiproc):
    """ compute the optimize after date for the a batch of files
        and then optimize them.
    """
    optimize_after = timestamp.get_optimize_after(path, True, None, arguments)
    return optimize_files(path, file_list, arguments, multiproc,
                          optimize_after)


def optimize_all_files(multiproc, arguments):
    """ Optimize the files from the arugments list in two batches.
        One for absolute paths which are probably outside the current
        working directory tree and one for relative files.
    """
    # Change dirs
    os.chdir(arguments.dir)
    cwd = os.getcwd()

    # Init records
    record_dirs = set()
    cwd_files = set()

    for filename in arguments.paths:
        # Record dirs to put timestamps in later
        if arguments.recurse and os.path.isdir(filename):
            record_dirs.add(filename)

        # Optimize all filenames that are not immediate descendants of
        #   the cwd and compute their optimize-after times individually.
        #   Otherwise add the files to the list to do next
        path_dn, path_fn = os.path.split(os.path.realpath(filename))
        if path_dn != cwd:
            optimize_files_after(path_dn, arguments, [path_fn], multiproc)
        else:
            cwd_files.add(path_fn)

    # Optimize immediate descendants with optimize after computed from
    # the current directory
    if len(cwd_files):
        optimize_files_after(cwd, arguments, cwd_files, multiproc)

    return record_dirs
