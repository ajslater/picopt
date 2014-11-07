#!/usr/bin/env python
"""
Runs pictures through image specific external optimizers
"""
from __future__ import print_function
from __future__ import division

import sys
import os
import argparse
import shutil
import subprocess
import multiprocessing
import copy
import zipfile
import traceback
import dateutil.parser
import time
import rarfile
from collections import namedtuple

try:
    from PIL import Image
except ImportError:
    import Image

__version__ = '1.1.3'

PROGRAM_NAME = 'picopt'

# Extensions
REMOVE_EXT = '.%s-remove' % PROGRAM_NAME
NEW_EXT = '.%s-optimized.png' % PROGRAM_NAME
ARCHIVE_TMP_DIR_PREFIX = PROGRAM_NAME+'_tmp_'
ARCHIVE_TMP_DIR_TEMPLATE = ARCHIVE_TMP_DIR_PREFIX+'%s'
NEW_ARCHIVE_SUFFIX = '%s-optimized.cbz' % PROGRAM_NAME
# Program args
MOZJPEG_ARGS = ['mozjpeg']
JPEGTRAN_ARGS = ['jpegtran', '-optimize']
JPEGRESCAN_ARGS = ['jpegrescan']
OPTIPNG_ARGS = ['optipng', '-o6', '-fix', '-preserve', '-force', '-quiet']
ADVPNG_ARGS = ['advpng', '-z', '-4', '-f']
PNGOUT_ARGS = ['pngout', '-q', '-force', '-y']
GIFSICLE_ARGS = ['gifsicle', '--optimize=3', '--batch']
# Formats
PNG_FORMATS = set(['PNG'])
SEQUENCED_TEMPLATE = '%s SEQUENCED'
GIF_FORMATS = set([SEQUENCED_TEMPLATE % 'GIF', 'GIF'])
LOSSLESS_FORMATS = set(('PNM', 'PPM', 'TIFF', 'BMP', 'GIF'))
PNG_CONVERTABLE_FORMATS = LOSSLESS_FORMATS | PNG_FORMATS
JPEG_FORMATS = set(['JPEG'])
CBR_EXT = '.cbr'
CBZ_EXT = '.cbz'
COMIC_EXTS = set((CBR_EXT, CBZ_EXT))
CBZ_FORMAT = 'CBZ'
CBR_FORMAT = 'CBR'
COMIC_FORMATS = set((CBZ_FORMAT, CBR_FORMAT))
FORMAT_DELIMETER = ','
DEFAULT_FORMATS = 'ALL'
ALL_DEFAULT_FORMATS = JPEG_FORMATS | GIF_FORMATS | PNG_CONVERTABLE_FORMATS
ALL_FORMATS = ALL_DEFAULT_FORMATS | COMIC_FORMATS
NONE_FORMAT = 'NONE'
ERROR_FORMAT = 'ERROR'
# Programs
PROGRAMS = ('optipng', 'pngout', 'mozjpeg', 'jpegrescan', 'jpegtran',
            'gifsicle', 'advpng')
RECORD_FILENAME = '.%s_timestamp' % PROGRAM_NAME
if sys.version > '3':
    LongInt = int
else:
    LongInt = long

ABBREVS = (
    (1 << LongInt(50), 'PiB'),
    (1 << LongInt(40), 'TiB'),
    (1 << LongInt(30), 'GiB'),
    (1 << LongInt(20), 'MiB'),
    (1 << LongInt(10), 'kiB'),
    (1, 'bytes')
)

ReportStats = namedtuple('ReportStats', ['final_filename', 'bytes_diff',
                                         'report_list'])
ExtArgs = namedtuple('ExtArgs', ['old_filename', 'new_filename', 'arguments'])


def humanize_bytes(num_bytes, precision=1):
    """
    from:
    http://code.activestate.com/recipes/
           577081-humanized-representation-of-a-number-of-num_bytes/
    Return a humanized string representation of a number of num_bytes.

    Assumes `from __future__ import division`.

    >>> humanize_bytes(1)
    '1 byte'
    >>> humanize_bytes(1024)
    '1.0 kB'
    >>> humanize_bytes(1024*123)
    '123.0 kB'
    >>> humanize_bytes(1024*12342)
    '12.1 MB'
    >>> humanize_bytes(1024*12342,2)
    '12.05 MB'
    >>> humanize_bytes(1024*1234,2)
    '1.21 MB'
    >>> humanize_bytes(1024*1234*1111,2)
    '1.31 GB'
    >>> humanize_bytes(1024*1234*1111,1)
    '1.3 GB'
    """

    if num_bytes == 0:
        return 'no bytes'
    if num_bytes == 1:
        return '1 byte'

    factored_bytes = 0
    factor_suffix = 'bytes'
    for factor, suffix in ABBREVS:
        if num_bytes >= factor:
            factored_bytes = num_bytes / factor
            factor_suffix = suffix
            break

    if factored_bytes == 1:
        precision = 0

    return '%.*f %s' % (precision, factored_bytes, factor_suffix)


def does_external_program_run(prog, arguments):
    """test to see if the external programs can be run"""
    try:
        null = open('/dev/null')
        subprocess.call([prog, '-h'], stdout=null, stderr=null)
        result = True
    except OSError:
        if arguments.verbose > 1:
            print("couldn't run %s" % prog)
        result = False

    return result


def program_reqs(arguments):
    """run the external program tester on the required binaries"""
    for program_name in PROGRAMS:
        val = getattr(arguments, program_name) \
            and does_external_program_run(program_name, arguments)
        setattr(arguments, program_name, val)

    do_png = arguments.optipng or arguments.pngout or arguments.advpng
    do_jpeg = arguments.mozjpeg or arguments.jpegrescan or arguments.jpegtran

    do_comics = arguments.comics

    if not do_png and not do_jpeg and not do_comics:
        print("All optimizers are not available or disabled.")
        exit(1)


def get_arguments():
    """parses the command line"""
    usage = "%(prog)s [arguments] [image files]"
    programs_str = ', '.join(PROGRAMS[:-1])+' and '+PROGRAMS[-1]
    description = "Uses "+programs_str+" if they are on the path."
    parser = argparse.ArgumentParser(usage=usage, description=description)
    parser.add_argument("-r", "--recurse", action="store_true",
                        dest="recurse", default=0,
                        help="Recurse down through directories ignoring the"
                        "image file arguments on the command line")
    parser.add_argument("-v", "--verbose", action="count",
                        dest="verbose", default=0,
                        help="Display more output. -v (default) and -vv "
                        "(noisy)")
    parser.add_argument("-Q", "--quiet", action="store_const",
                        dest="verbose", const=-1,
                        help="Display little to no output")
    parser.add_argument("-a", "--enable_advpng", action="store_true",
                        dest="advpng", default=0,
                        help="Optimize with advpng (disabled by default)")
    parser.add_argument("-c", "--comics", action="store_true",
                        dest="comics", default=0,
                        help="Also optimize comic book archives (cbz & cbr)")
    parser.add_argument("-f", "--formats", action="store", dest="formats",
                        default=DEFAULT_FORMATS,
                        help="Only optimize images of the specifed '%s' "
                        "delimited formats from: %s" %
                        (FORMAT_DELIMETER, ', '.join(sorted(ALL_FORMATS))))
    parser.add_argument("-O", "--disable_optipng", action="store_false",
                        dest="optipng", default=1,
                        help="Do not optimize with optipng")
    parser.add_argument("-P", "--disable_pngout", action="store_false",
                        dest="pngout", default=1,
                        help="Do not optimize with pngout")
    parser.add_argument("-J", "--disable_jpegrescan", action="store_false",
                        dest="jpegrescan", default=1,
                        help="Do not optimize with jpegrescan")
    parser.add_argument("-E", "--disable_progressive", action="store_false",
                        dest="jpegtran_prog", default=1,
                        help="Don't try to reduce size by making "
                        "progressive JPEGs with jpegtran")
    parser.add_argument("-Z", "--disable_mozjpeg", action="store_false",
                        dest="mozjpeg", default=1,
                        help="Do not optimize with mozjpeg")
    parser.add_argument("-T", "--disable_jpegtran", action="store_false",
                        dest="jpegtran", default=1,
                        help="Do not optimize with jpegtran")
    parser.add_argument("-G", "--disable_gifsicle", action="store_false",
                        dest="gifsicle", default=1,
                        help="disable optimizing animated GIFs")
    parser.add_argument("-Y", "--disable_convert_type", action="store_const",
                        dest="to_png_formats",
                        const=PNG_FORMATS, default=PNG_CONVERTABLE_FORMATS,
                        help="Do not convert other lossless formats like "
                        " %s to PNG when optimizing. By default, %s"
                        " does convert these formats to PNG" %
                        (', '.join(LOSSLESS_FORMATS), PROGRAM_NAME))
    parser.add_argument("-S", "--disable_follow_symlinks",
                        action="store_false",
                        dest="follow_symlinks", default=1,
                        help="disable following symlinks for files and "
                        "directories")
    parser.add_argument("-d", "--dir", action="store", dest="dir",
                        default=os.getcwd(),
                        help="Directory to change to before optimiziaton")
    parser.add_argument("-b", "--bigger", action="store_true",
                        dest="bigger", default=0,
                        help="Save optimized files that are larger than "
                        "the originals")
    parser.add_argument("-t", "--record_timestamp", action="store_true",
                        dest="record_timestamp", default=0,
                        help="Store the time of the optimization of full "
                        "directories in directory local dotfiles.")
    parser.add_argument("-D", "--optimize_after", action="store",
                        dest="optimize_after", default=None,
                        help="only optimize files after the specified "
                        "timestamp. Supercedes -t")
    parser.add_argument("-N", "--noop", action="store_true",
                        dest="test", default=0,
                        help="Do not replace files with optimized versions")
    parser.add_argument("-l", "--list", action="store_true",
                        dest="list_only", default=0,
                        help="Only list files that would be optimized")
    parser.add_argument("-V", "--version", action="version",
                        version=__version__,
                        help="display the version number")
    parser.add_argument("-M", "--destroy_metadata", action="store_true",
                        dest="destroy_metadata", default=0,
                        help="*Destroy* metadata like EXIF and JFIF")
    parser.add_argument("paths", metavar="path", type=str, nargs="+",
                        help="File or directory paths to optimize")

    return parser.parse_args()


def process_arguments(arguments):
    """ Recomputer special cases for input arguments """
    program_reqs(arguments)

    arguments.verbose += 1
    arguments.paths = set(arguments.paths)
    arguments.archive_name = None

    if arguments.formats == DEFAULT_FORMATS:
        arguments.formats = arguments.to_png_formats | JPEG_FORMATS | \
            GIF_FORMATS
    else:
        arguments.formats = arguments.formats.upper().split(FORMAT_DELIMETER)

    if arguments.comics:
        arguments.formats = arguments.formats | COMIC_FORMATS

    if arguments.optimize_after is not None:
        try:
            after_dt = dateutil.parser.parse(arguments.optimize_after)
            arguments.optimize_after = time.mktime(after_dt.timetuple())
        except Exception as ex:
            print(ex)
            print('Could not parse date to optimize after.')
            exit(1)

    # Make a rough guess about weather or not to invoke multithreding
    # jpegrescan '-t' uses three threads
    # one off multithread switch bcaseu this is the only one right now
    files_in_paths = 0
    non_file_in_paths = False
    for filename in arguments.paths:
        if os.path.isfile(filename):
            files_in_paths += 1
        else:
            non_file_in_paths = True
    arguments.jpegrescan_multithread = not non_file_in_paths and \
        multiprocessing.cpu_count() - (files_in_paths*3) > -1

    return arguments


def replace_ext(filename, new_ext):
    """replaces the file extention"""
    filename_base = os.path.splitext(filename)[0]
    new_filename = '{}.{}'.format(filename_base, new_ext)
    return new_filename


def new_percent_saved(report_stats):
    """spits out how much space the optimization saved"""
    size_in = report_stats.bytes_diff['in']
    if size_in != 0:
        size_out = report_stats.bytes_diff['out']
        ratio = size_out / size_in
    else:
        ratio = 0
    percent_saved = (1 - ratio) * 100

    size_saved_kb = humanize_bytes(size_in - size_out)
    result = '%.*f%s (%s)' % (2, percent_saved, '%', size_saved_kb)
    return result


def run_ext(args):
    """run EXTERNAL program"""
    subprocess.call(args, stdout=subprocess.PIPE)


def pngout(ext_args):
    """runs the EXTERNAL program pngout on the file"""
    args = PNGOUT_ARGS + [ext_args.old_filename, ext_args.new_filename]
    run_ext(args)


def optipng(ext_args):
    """runs the EXTERNAL program optipng on the file"""
    args = OPTIPNG_ARGS + [ext_args.new_filename]
    run_ext(args)


def advpng(ext_args):
    """runs the EXTERNAL program advpng on the file"""
    args = ADVPNG_ARGS + [ext_args.new_filename]
    run_ext(args)


def gifsicle(ext_args):
    """runs the EXTERNAL program gifsicle"""
    args = GIFSICLE_ARGS + [ext_args.new_filename]
    run_ext(args)


def mozjpeg(ext_args):
    """create argument list for mozjpeg"""
    args = copy.copy(MOZJPEG_ARGS)
    if ext_args.arguments.destroy_metadata:
        args += ["-copy", "none"]
    else:
        args += ["-copy", "all"]
    args += ['-outfile']
    args += [ext_args.new_filename, ext_args.old_filename]
    run_ext(args)


def jpegtran(ext_args):
    """create argument list for jpegtran"""
    args = copy.copy(JPEGTRAN_ARGS)
    if ext_args.arguments.destroy_metadata:
        args += ["-copy", "none"]
    else:
        args += ["-copy", "all"]
    if ext_args.arguments.jpegtran_prog:
        args += ["-progressive"]
    args += ['-outfile']
    args += [ext_args.new_filename, ext_args.old_filename]
    run_ext(args)


def jpegrescan(ext_args):
    """runs the EXTERNAL program jpegrescan"""
    args = copy.copy(JPEGRESCAN_ARGS)
    if ext_args.arguments.jpegrescan_multithread:
        args += ['-t']
    if ext_args.arguments.destroy_metadata:
        args += ['-s']
    args += [ext_args.old_filename, ext_args.new_filename]
    run_ext(args)


def is_format_selected(image_format, formats, arguments, mode):
    """returns a boolean indicating weather or not the image format
    was selected by the command line arguments"""
    intersection = formats & arguments.formats
    result = (image_format in intersection) and mode
    return result


def cleanup_after_optimize(filename, new_filename, arguments):
    """report results. replace old file with better one or discard new wasteful
       file"""

    bytes_diff = {'in': 0, 'out': 0}
    final_filename = filename
    try:
        filesize_in = os.stat(filename).st_size
        filesize_out = os.stat(new_filename).st_size
        bytes_diff['in'] = filesize_in
        bytes_diff['out'] = filesize_in  # overwritten on succes below
        if (filesize_out > 0) and ((filesize_out < filesize_in)
                                   or arguments.bigger):
            old_image_format = get_image_format(filename, arguments)
            new_image_format = get_image_format(new_filename, arguments)
            if old_image_format != new_image_format:
                final_filename = replace_ext(filename,
                                             new_image_format.lower())
            rem_filename = filename + REMOVE_EXT
            if not arguments.test:
                os.rename(filename, rem_filename)
                os.rename(new_filename, final_filename)
                os.remove(rem_filename)
            else:
                os.remove(new_filename)

            bytes_diff['out'] = filesize_out  # only on completion
        else:
            os.remove(new_filename)
    except OSError as ex:
        print(ex)

    return ReportStats._make([final_filename, bytes_diff, []])


def optimize_image_external(filename, arguments, func):
    """this could be a decorator"""
    new_filename = os.path.normpath(filename + NEW_EXT)
    shutil.copy2(filename, new_filename)

    ext_args = ExtArgs._make([filename, new_filename, arguments])
    func(ext_args)

    report_stats = cleanup_after_optimize(filename, new_filename, arguments)
    percent = new_percent_saved(report_stats)
    if percent != 0:
        report = '%s: %s' % (func.__name__, percent)
    else:
        report = ''
    report_stats.report_list.append(report)

    return report_stats


def optimize_gif(filename, arguments):
    """run EXTERNAL programs to optimize animated gifs"""
    if arguments.gifsicle:
        report_stats = optimize_image_external(filename, arguments,
                                               gifsicle)
    else:
        rep = ['Skipping animated GIF: %s' % filename]
        bytes_diff = {'in': 0, 'out': 0}
        report_stats = ReportStats._make([filename, bytes_diff, [rep]])

    return report_stats


def optimize_png(filename, arguments):
    """run EXTERNAL programs to optimize lossless formats to PNGs"""
    filesize_in = os.stat(filename).st_size
    report_stats = None

    for ext_prog in ('optipng', 'advpng', 'pngout'):
        if not getattr(arguments, ext_prog):
            continue
        report_stats = optimize_image_external(
            filename, arguments, globals()[ext_prog])
        filename = report_stats.final_filename

    if report_stats is not None:
        report_stats.bytes_diff['in'] = filesize_in
    else:
        bytes_diff = {'in': 0, 'out': 0}
        rep = 'Skipping file: %s' % filename
        report_stats = ReportStats._make([filename, bytes_diff, rep])

    return report_stats


def optimize_jpeg(filename, arguments):
    """run EXTERNAL programs to optimize jpeg formats"""
    final_filename = filename
    if arguments.mozjpeg:
        report_stats = optimize_image_external(
            final_filename, arguments, mozjpeg)
    elif arguments.jpegrescan:
        report_stats = optimize_image_external(
            final_filename, arguments, jpegrescan)
    elif arguments.jpegtran_prog or arguments.jpegtran:
        report_stats = optimize_image_external(
            final_filename, arguments, jpegtran)
    else:
        rep = ['Skipping JPEG file: %s' % filename]
        bytes_diff = {'in': 0, 'out': 0}
        report_stats = ReportStats._make([filename, bytes_diff, [rep]])

    return report_stats


def optimize_image(arg):
    """optimizes a given image from a filename"""
    try:
        filename, image_format, arguments, total_bytes_in, total_bytes_out, \
            nag_about_gifs = arg

        if is_format_selected(image_format, arguments.to_png_formats,
                              arguments, arguments.optipng or
                              arguments.pngout):
            report_stats = optimize_png(filename, arguments)
        elif is_format_selected(image_format, JPEG_FORMATS, arguments,
                                arguments.mozjpeg or arguments.jpegrescan
                                or arguments.jpegtran):
            report_stats = optimize_jpeg(filename, arguments)
        elif is_format_selected(image_format, GIF_FORMATS, arguments,
                                arguments.gifsicle):
            # this captures still GIFs too if not caught above
            report_stats = optimize_gif(filename, arguments)
            nag_about_gifs.set(True)
        else:
            if arguments.verbose > 1:
                print(filename, image_format)  # image.mode)
                print("\tFile format not selected.")
            return

        optimize_accounting(report_stats, total_bytes_in, total_bytes_out,
                            arguments)
    except Exception as exc:
        print(exc)
        traceback.print_exc(exc)
        raise exc


def truncate_cwd(full_filename, arguments):
    """ remove the cwd from the full filenam """
    truncated_filename = full_filename.split(arguments.dir, 1)[1]
    truncated_filename = truncated_filename.split(os.sep, 1)[1]
    return truncated_filename


def optimize_accounting(report_stats, total_bytes_in, total_bytes_out,
                        arguments):
    """record the percent saved, print it and add it to the totals"""
    if arguments.verbose:
        report = ''
        if arguments.archive_name is not None:
            truncated_filename = report_stats.final_filename.split(
                ARCHIVE_TMP_DIR_PREFIX, 1)[1]
            truncated_filename = truncated_filename.split(os.sep, 1)[1]
            report += '  %s: ' % arguments.archive_name
        elif arguments.dir in report_stats.final_filename:
            truncated_filename = truncate_cwd(report_stats.final_filename,
                                              arguments)
        else:
            truncated_filename = report_stats.final_filename

        report += '%s: ' % truncated_filename
        total = new_percent_saved(report_stats)
        if total:
            report += total
        else:
            report += '0%'
        if arguments.test:
            report += ' could be saved.'
        if arguments.verbose > 1:
            tools_report = ', '.join(report_stats.report_list)
            if tools_report:
                report += '\n\t' + tools_report
        print(report)

    total_bytes_in.set(total_bytes_in.get() + report_stats.bytes_diff['in'])
    total_bytes_out.set(total_bytes_out.get() + report_stats.bytes_diff['out'])


def is_image_sequenced(image):
    """determines if the image is a sequenced image"""
    try:
        image.seek(1)
        image.seek(0)
        result = True
    except EOFError:
        result = False

    return result


def get_image_format(filename, arguments):
    """gets the image format"""
    image = None
    bad_image = 1
    image_format = NONE_FORMAT
    sequenced = False
    try:
        bad_image = Image.open(filename).verify()
        image = Image.open(filename)
        image_format = image.format
        sequenced = is_image_sequenced(image)
    except (OSError, IOError, AttributeError):
        pass

    if sequenced:
        image_format = SEQUENCED_TEMPLATE % image_format
    elif image is None or bad_image or image_format == NONE_FORMAT:
        image_format = ERROR_FORMAT
        filename_ext = os.path.splitext(filename)[-1].lower()
        if filename_ext in COMIC_EXTS:
            if zipfile.is_zipfile(filename):
                image_format = CBZ_FORMAT
            elif rarfile.is_rarfile(filename):
                image_format = CBR_FORMAT
        if (arguments.verbose > 1) and image_format == ERROR_FORMAT and \
                (not arguments.list_only):
            print(filename, "doesn't look like an image or comic archive.")
    return image_format


def detect_file(filename, arguments):
    """decides what to do with the file"""
    image_format = get_image_format(filename, arguments)

    if image_format in arguments.formats:
        return image_format

    if image_format in (NONE_FORMAT, ERROR_FORMAT):
        return

    if arguments.verbose > 1 and not arguments.list_only:
        print(filename, image_format, 'is not a enabled image or '
              'comic archive type.')


def get_archive_tmp_dir(filename):
    """ get the name of the working dir to use for this filename"""
    head, tail = os.path.split(filename)
    return os.path.join(head, ARCHIVE_TMP_DIR_TEMPLATE % tail)


def comic_archive_compress(args):
    """called back by every optimization inside a comic archive.
       when they're all done it creates the new archive and cleans up.
    """

    try:
        filename, total_bytes_in, total_bytes_out, arguments = args

        tmp_dir = get_archive_tmp_dir(filename)

        # archive into new filename
        new_filename = replace_ext(filename, NEW_ARCHIVE_SUFFIX)

        if arguments.verbose:
            print('Rezipping archive', end='')
        with zipfile.ZipFile(new_filename, 'w',
                             compression=zipfile.ZIP_DEFLATED) as new_zf:
            root_len = len(os.path.abspath(tmp_dir))
            for root, dirs, files in os.walk(tmp_dir):
                archive_root = os.path.abspath(root)[root_len:]
                for fname in files:
                    fullpath = os.path.join(root, fname)
                    archive_name = os.path.join(archive_root, fname)
                    if arguments.verbose:
                        print('.', end='')
                    new_zf.write(fullpath, archive_name, zipfile.ZIP_DEFLATED)

        # Cleanup tmpdir
        if os.path.isdir(tmp_dir):
            if arguments.verbose:
                print('.', end='')
            shutil.rmtree(tmp_dir)
        if arguments.verbose:
            print('done.')

        report_stats = cleanup_after_optimize(filename, new_filename,
                                              arguments)
        optimize_accounting(report_stats, total_bytes_in, total_bytes_out,
                            arguments)
    except Exception as exc:
        print(exc)
        traceback.print_exc(exc)
        raise exc


def comic_archive_uncompress(filename, image_format, arguments):
    """ uncompress comic archives and return the name of the working
        directory we uncompressed into """

    if not arguments.comics:
        report = ['Skipping archive file: %s' % filename]
        report_list = [report]
        bytes_diff = {'in': 0, 'out': 0}
        return (bytes_diff, report_list)

    if arguments.verbose:
        truncated_filename = truncate_cwd(filename, arguments)
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

    if arguments.verbose:
        print('done')

    return os.path.basename(tmp_dir)


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


def optimize_dir(filename_full, arguments, multiproc, optimize_after):
    """ Recursively optimize a directory """
    if not arguments.recurse:
        return set()
    next_dir_list = os.listdir(filename_full)
    next_dir_list.sort()
    optimize_after = get_optimize_after(filename_full, False,
                                        optimize_after, arguments)
    return optimize_files(filename_full, next_dir_list, arguments,
                          multiproc, optimize_after)


def optimize_comic_archive(filename_full, image_format, arguments, multiproc,
                           optimize_after):
    """ Optimize a comic archive """
    tmp_dir_basename = comic_archive_uncompress(filename_full,
                                                image_format, arguments)
    # recurse into comic archive even if flag not set
    archive_arguments = copy.deepcopy(arguments)
    archive_arguments.recurse = True
    archive_arguments.archive_name = os.path.basename(filename_full)

    # optimize contents of comic archive
    dirname = os.path.dirname(filename_full)
    result_set = optimize_files(dirname, [tmp_dir_basename],
                                archive_arguments, multiproc,
                                optimize_after)

    # I'd like to stuff this waiting into the compression process,
    # but process results don't serialize. :(
    for result in result_set:
        result.wait()

    args = (filename_full, multiproc['in'], multiproc['out'], arguments)
    return multiproc['pool'].apply_async(comic_archive_compress, args=(args,))


def optimize_file(filename_full, arguments, multiproc, optimize_after):
    """ Optimize an individual file """
    if optimize_after is not None:
        mtime = os.stat(filename_full).st_mtime
        if mtime <= optimize_after:
            return

    image_format = detect_file(filename_full, arguments)
    if not image_format:
        return

    if arguments.list_only:
        # list only
        print("%s : %s" % (filename_full, image_format))
    elif is_format_selected(image_format, COMIC_FORMATS,
                            arguments, arguments.comics):
        return optimize_comic_archive(filename_full, image_format,
                                      arguments, multiproc, optimize_after)
    else:
        # regular image
        args = [filename_full, image_format, arguments,
                multiproc['in'], multiproc['out'], multiproc['nag_about_gifs']]
        return multiproc['pool'].apply_async(optimize_image, args=(args,))


def optimize_files(cwd, filter_list, arguments, multiproc, optimize_after):
    """sorts through a list of files, decends directories and
       calls the optimizer on the extant files"""

    result_set = set()
    for filename in filter_list:

        filename_full = os.path.join(cwd, filename)
        filename_full = os.path.normpath(filename_full)

        if not arguments.follow_symlinks and os.path.islink(filename_full):
            continue
        elif os.path.basename(filename_full) == RECORD_FILENAME:
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


def report_totals(bytes_in, bytes_out, arguments, nag_about_gifs):
    """report the total number and percent of bytes saved"""
    if bytes_in:
        bytes_saved = bytes_in - bytes_out
        percent_bytes_saved = bytes_saved / bytes_in * 100
        msg = ''
        if arguments.test:
            if percent_bytes_saved > 0:
                msg += "Could save"
            elif percent_bytes_saved == 0:
                msg += "Could even out for"
            else:
                msg += "Could lose"
        else:
            if percent_bytes_saved > 0:
                msg += "Saved"
            elif percent_bytes_saved == 0:
                msg += "Evened out"
            else:
                msg = "Lost"
        msg += " a total of %s or %.*f%s" % (humanize_bytes(bytes_saved),
                                             2, percent_bytes_saved, '%')
        if arguments.verbose:
            print(msg)
            if arguments.test:
                print("Test run did not change any files.")

    else:
        if arguments.verbose:
            print("Didn't optimize any files.")

    if nag_about_gifs and arguments.verbose:
        print("Most animated GIFS would be better off converted to"
              " HTML5 video")


def optimize_files_after(path, arguments, file_list, multiproc):
    """ compute the optimize after date for the a batch of files
        and then optimize them.
    """
    optimize_after = get_optimize_after(path, True, None, arguments)
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
            optimize_files_after(path_dn, arguments,
                                 [path_fn], multiproc)
        else:
            cwd_files.add(path_fn)

    # Optimize immediate descendants with optimize after computed from
    # the current directory
    if len(cwd_files):
        optimize_files_after(cwd, arguments, cwd_files, multiproc)

    return record_dirs


def run_main(raw_arguments):
    """ The main optimization call """

    arguments = process_arguments(raw_arguments)

    # Setup Multiprocessing
    manager = multiprocessing.Manager()
    total_bytes_in = manager.Value(int, 0)
    total_bytes_out = manager.Value(int, 0)
    nag_about_gifs = manager.Value(bool, False)
    pool = multiprocessing.Pool()

    multiproc = {'pool': pool, 'in': total_bytes_in, 'out': total_bytes_out,
                 'nag_about_gifs': nag_about_gifs}

    # Optimize Files
    record_dirs = optimize_all_files(multiproc, arguments)

    # Shut down multiprocessing
    pool.close()
    pool.join()

    # Write timestamps
    for filename in record_dirs:
        record_timestamp(filename, arguments)

    # Finish by reporting totals
    report_totals(multiproc['in'].get(), multiproc['out'].get(),
                  arguments, multiproc['nag_about_gifs'].get())


def main():
    """main"""
    raw_arguments = get_arguments()
    run_main(raw_arguments)


if __name__ == '__main__':
    main()
