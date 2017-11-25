"""Optimize comic archives."""
from __future__ import absolute_import, division, print_function

import os
import shutil
import traceback
import zipfile

import rarfile

from .. import PROGRAM_NAME, files, stats
from ..settings import Settings
from ..stats import ReportStats

_CBZ_FORMAT = 'CBZ'
_CBR_FORMAT = 'CBR'
FORMATS = set((_CBZ_FORMAT, _CBR_FORMAT))

_CBR_EXT = '.cbr'
_CBZ_EXT = '.cbz'
_COMIC_EXTS = set((_CBR_EXT, _CBZ_EXT))
OUT_EXT = _CBZ_EXT

_ARCHIVE_TMP_DIR_PREFIX = PROGRAM_NAME+'_tmp_'
_ARCHIVE_TMP_DIR_TEMPLATE = _ARCHIVE_TMP_DIR_PREFIX+'{}'
_NEW_ARCHIVE_SUFFIX = '{}-optimized{}'.format(PROGRAM_NAME, OUT_EXT)


def comics():
    """
    Dummy Comic optimizer.

    Not used because comics are special and use walk.walk_comic_archive
    But currently neccissary to keep detect_format._is_program_selected()
    working
    """
    pass


PROGRAMS = (comics,)
BEST_ONLY = False


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
    return os.path.join(head, _ARCHIVE_TMP_DIR_TEMPLATE.format(tail))


def comic_archive_uncompress(filename, image_format):
    """
    Uncompress comic archives.

    Return the name of the working directory we uncompressed into.
    """
    if not Settings.comics:
        report = ['Skipping archive file: {}'.format(filename)]
        return None, ReportStats(filename, report=report)

    if Settings.verbose:
        truncated_filename = stats.truncate_cwd(filename)
        print("Extracting {}...".format(truncated_filename), end='')

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
        report = '{} {} is not a good format'.format(filename, image_format)
        return None, ReportStats(filename, report=report)

    if Settings.verbose:
        print('done')

    return tmp_dir, None


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
        filename, old_format, settings, nag_about_gifs = args
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
        report_stats.nag_about_gifs = nag_about_gifs
        stats.report_saved(report_stats)
        return report_stats
    except Exception as exc:
        print(exc)
        traceback.print_exc(exc)
        raise exc
