"""Optimize comic archives."""
from __future__ import print_function

import os
import zipfile
import shutil
import traceback

import rarfile

from .. import stats
from ..settings import Settings
from .. import PROGRAM_NAME
from .. import files

# Extensions
_ARCHIVE_TMP_DIR_PREFIX = PROGRAM_NAME+'_tmp_'
_ARCHIVE_TMP_DIR_TEMPLATE = _ARCHIVE_TMP_DIR_PREFIX+'%s'
_NEW_ARCHIVE_SUFFIX = '%s-optimized.cbz' % PROGRAM_NAME

_CBR_EXT = '.cbr'
_CBZ_EXT = '.cbz'
_COMIC_EXTS = set((_CBR_EXT, _CBZ_EXT))

_CBZ_FORMAT = 'CBZ'
_CBR_FORMAT = 'CBR'
FORMATS = set((_CBZ_FORMAT, _CBR_FORMAT))


def comics():
    """
    Dummy Comic optimizer.

    Not used because comics are special and use walk.walk_comic_archive
    But currently neccissary to keep detect_format._is_program_selected()
    working
    """
    pass

PROGRAMS = (comics,)

def get_comic_format(filename):
    """Return the comic format if it is a comic archive."""
    image_format = None
    filename_ext = os.path.splitext(filename)[-1].lower()
    if filename_ext in _COMIC_EXTS:
        if zipfile.is_zipfile(filename):
            image_format = _CBZ_FORMAT
        elif rarfile.is_rarfile(filename):
            image_format = _CBR_FORMAT
    return image_format


def _get_archive_tmp_dir(filename):
    """Get the name of the working dir to use for this filename."""
    head, tail = os.path.split(filename)
    return os.path.join(head, _ARCHIVE_TMP_DIR_TEMPLATE % tail)


def comic_archive_uncompress(filename, image_format):
    """
    Uncompress comic archives.

    Return the name of the working directory we uncompressed into.
    """
    if not Settings.comics:
        report = ['Skipping archive file: %s' % filename]
        report_list = [report]
        bytes_diff = {'in': 0, 'out': 0}
        return (bytes_diff, report_list)

    if Settings.verbose:
        truncated_filename = stats.truncate_cwd(filename)
        print("Extracting %s..." % truncated_filename, end='')

    # create the tmpdir
    tmp_dir = _get_archive_tmp_dir(filename)
    if os.path.isdir(tmp_dir):
        shutil.rmtree(tmp_dir)
    os.mkdir(tmp_dir)

    # extract archvie into the tmpdir
    if image_format == _CBZ_FORMAT:
        with zipfile.ZipFile(filename, 'r') as zfile:
            zfile.extractall(tmp_dir)
    elif image_format == _CBR_FORMAT:
        with rarfile.RarFile(filename, 'r') as rfile:
            rfile.extractall(tmp_dir)
    else:
        report = '%s %s is not a good format' % (filename, image_format)
        report_list = [report]
        bytes_diff = {'in': 0, 'out': 0}
        return (bytes_diff, report_list)

    if Settings.verbose:
        print('done')

    return tmp_dir


def _comic_archive_write_zipfile(new_filename, tmp_dir):
    """Zip up the files in the tempdir into the new filename."""
    if Settings.verbose:
        print('Rezipping archive', end='')
    with zipfile.ZipFile(new_filename, 'w',
                         compression=zipfile.ZIP_DEFLATED) as new_zf:
        root_len = len(os.path.abspath(tmp_dir))
        for r_d_f in os.walk(tmp_dir):
            root = r_d_f[0]
            filenames = r_d_f[2]
            archive_root = os.path.abspath(root)[root_len:]
            for fname in filenames:
                fullpath = os.path.join(root, fname)
                archive_name = os.path.join(archive_root, fname)
                if Settings.verbose:
                    print('.', end='')
                new_zf.write(fullpath, archive_name, zipfile.ZIP_DEFLATED)


def comic_archive_compress(args):
    """
    Called back by every optimization inside a comic archive.

    When they're all done it creates the new archive and cleans up.
    """
    try:
        filename, total_bytes_in, total_bytes_out, old_format, \
            settings = args
        Settings.update(settings)
        tmp_dir = _get_archive_tmp_dir(filename)

        # archive into new filename
        new_filename = files.replace_ext(filename, _NEW_ARCHIVE_SUFFIX)

        _comic_archive_write_zipfile(new_filename, tmp_dir)

        # Cleanup tmpdir
        if os.path.isdir(tmp_dir):
            if Settings.verbose:
                print('.', end='')
            shutil.rmtree(tmp_dir)
        if Settings.verbose:
            print('done.')

        report_stats = files.cleanup_after_optimize(
            filename, new_filename, old_format, _CBZ_FORMAT)
        stats.optimize_accounting(report_stats, total_bytes_in,
                                  total_bytes_out)
    except Exception as exc:
        print(exc)
        traceback.print_exc(exc)
        raise exc
