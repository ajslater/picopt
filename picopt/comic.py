"""
Optimize comic archives
"""
from __future__ import print_function

import os
import rarfile
import shutil
import traceback
import zipfile

import walk
import optimize
import stats
from settings import Settings
import name

# Extensions
ARCHIVE_TMP_DIR_PREFIX = name.PROGRAM_NAME+'_tmp_'
ARCHIVE_TMP_DIR_TEMPLATE = ARCHIVE_TMP_DIR_PREFIX+'%s'
NEW_ARCHIVE_SUFFIX = '%s-optimized.cbz' % name.PROGRAM_NAME

CBR_EXT = '.cbr'
CBZ_EXT = '.cbz'
COMIC_EXTS = set((CBR_EXT, CBZ_EXT))

CBZ_FORMAT = 'CBZ'
CBR_FORMAT = 'CBR'
FORMATS = set((CBZ_FORMAT, CBR_FORMAT))


def comics():
    pass

PROGRAMS = (comics,)


def get_comic_format(filename):
    """ return the comic format if it is a comic archive  """
    image_format = None
    filename_ext = os.path.splitext(filename)[-1].lower()
    if filename_ext in COMIC_EXTS:
        if zipfile.is_zipfile(filename):
            image_format = CBZ_FORMAT
        elif rarfile.is_rarfile(filename):
            image_format = CBR_FORMAT
    return image_format


def get_archive_tmp_dir(filename):
    """ get the name of the working dir to use for this filename"""
    head, tail = os.path.split(filename)
    return os.path.join(head, ARCHIVE_TMP_DIR_TEMPLATE % tail)


def comic_archive_uncompress(filename, image_format):
    """ uncompress comic archives and return the name of the working
        directory we uncompressed into """

    if not Settings.comics:
        report = ['Skipping archive file: %s' % filename]
        report_list = [report]
        bytes_diff = {'in': 0, 'out': 0}
        return (bytes_diff, report_list)

    if Settings.verbose:
        truncated_filename = stats.truncate_cwd(filename)
        print("Extracting %s..." % truncated_filename, end='')

    # create the tmpdir
    tmp_dir = get_archive_tmp_dir(filename)
    if os.path.isdir(tmp_dir):
        shutil.rmtree(tmp_dir)
    os.mkdir(tmp_dir)

    # extract archvie into the tmpdir
    if image_format == CBZ_FORMAT:
        with zipfile.ZipFile(filename, 'r') as zfile:
            zfile.extractall(tmp_dir)
    elif image_format == CBR_FORMAT:
        with rarfile.RarFile(filename, 'r') as rfile:
            rfile.extractall(tmp_dir)
    else:
        report = '%s %s is not a good format' % (filename, image_format)
        report_list = [report]
        bytes_diff = {'in': 0, 'out': 0}
        return (bytes_diff, report_list)

    if Settings.verbose:
        print('done')

    return os.path.basename(tmp_dir)


def comic_archive_write_zipfile(new_filename, tmp_dir):
    """ Zip up the files in the tempdir into the new filename """
    if Settings.verbose:
        print('Rezipping archive', end='')
    with zipfile.ZipFile(new_filename, 'w',
                         compression=zipfile.ZIP_DEFLATED) as new_zf:
        root_len = len(os.path.abspath(tmp_dir))
        for root, dirs, filenames in os.walk(tmp_dir):
            archive_root = os.path.abspath(root)[root_len:]
            for fname in filenames:
                fullpath = os.path.join(root, fname)
                archive_name = os.path.join(archive_root, fname)
                if Settings.verbose:
                    print('.', end='')
                new_zf.write(fullpath, archive_name, zipfile.ZIP_DEFLATED)


def comic_archive_compress(args):
    """called back by every optimization inside a comic archive.
       when they're all done it creates the new archive and cleans up.
    """

    try:
        filename, total_bytes_in, total_bytes_out, image_format, \
            settings = args
        Settings.update(settings)
        tmp_dir = get_archive_tmp_dir(filename)
        # archive into new filename
        new_filename = optimize.replace_ext(filename, NEW_ARCHIVE_SUFFIX)

        comic_archive_write_zipfile(new_filename, tmp_dir)

        # Cleanup tmpdir
        if os.path.isdir(tmp_dir):
            if Settings.verbose:
                print('.', end='')
            shutil.rmtree(tmp_dir)
        if Settings.verbose:
            print('done.')

        report_stats = optimize.cleanup_after_optimize(
            filename, new_filename, image_format)
        stats.optimize_accounting(report_stats, total_bytes_in,
                                  total_bytes_out)
    except Exception as exc:
        print(exc)
        traceback.print_exc(exc)
        raise exc


def walk_comic_archive(filename_full, image_format, multiproc,
                       optimize_after):
    """ Optimize a comic archive """
    tmp_dir_basename = comic_archive_uncompress(filename_full,
                                                image_format)

    # optimize contents of comic archive
    dirname = os.path.dirname(filename_full)
    result_set = walk.walk_files(dirname, [tmp_dir_basename],
                                 multiproc, optimize_after, True)

    # I'd like to stuff this waiting into the compression process,
    # but process results don't serialize. :(
    for result in result_set:
        result.wait()

    args = (filename_full, multiproc['in'], multiproc['out'], image_format,
            Settings)
    return multiproc['pool'].apply_async(comic_archive_compress, args=(args,))
