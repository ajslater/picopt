#!/usr/bin/env python
"""
Runs pictures through image specific external optimizers
"""
from __future__ import print_function
from __future__ import division

import sys
import os
import optparse
import shutil
import subprocess
import multiprocessing
import copy
import zipfile
import traceback
import dateutil.parser
import time

import Image
import ImageFile
import rarfile

__version__ = '0.11.1'

PROGRAM_NAME = 'picopt'

# Extensions
REMOVE_EXT = '.%s-remove' % PROGRAM_NAME
NEW_EXT = '.%s-optimized.png' % PROGRAM_NAME
ARCHIVE_TMP_DIR_TEMPLATE = PROGRAM_NAME+'_tmp_%s'
NEW_ARCHIVE_SUFFIX = '%s-optimized.cbz' % PROGRAM_NAME
# Program args
JPEGTRAN_OPTI_ARGS = ['jpegtran', '-copy', 'all', '-optimize',
                      '-outfile']
JPEGTRAN_PROG_ARGS = ['jpegtran', '-copy', 'all', '-optimize',
                      '-progressive', '-outfile']
JPEGRESCAN_ARGS = ['jpegrescan']
OPTIPNG_ARGS = ['optipng', '-o6', '-fix', '-preserve', '-force', '-quiet']
ADVPNG_ARGS = ['advpng', '-z', '-4', '-f']
PNGOUT_ARGS = ['pngout', '-q', '-force', '-y']
GIFSICLE_ARGS = ['gifsicle', '--optimize=3', '--batch']
# Formats
PNG_FORMATS = set(['PNG'])
SEQUENCED_TEMPLATE = '%s SEQUENCED'
GIF_FORMATS = set([SEQUENCED_TEMPLATE % 'GIF', 'GIF'])
PNG_CONVERTABLE_FORMATS = set(('PNM', 'TIFF', 'BMP', 'GIF')) | PNG_FORMATS
JPEG_FORMATS = set(['JPEG'])
CBR_EXT = '.cbr'
CBZ_EXT = '.cbz'
COMIC_EXTS = set((CBR_EXT, CBZ_EXT))
CBZ_FORMAT = 'CBZ'
CBR_FORMAT = 'CBR'
COMIC_FORMATS = set((CBZ_FORMAT, CBR_FORMAT))
FORMAT_DELIMETER = ','
DEFAULT_FORMATS = 'ALL'
# Programs
PROGRAMS = ('optipng', 'pngout', 'jpegrescan', 'jpegtran', 'gifsicle',
            'advpng')
RECORD_FILENAME = '.%s_timestamp' % PROGRAM_NAME
if sys.version > '3':
    long = int

ABBREVS = (
    (1 << long(50), 'PiB'),
    (1 << long(40), 'TiB'),
    (1 << long(30), 'GiB'),
    (1 << long(20), 'MiB'),
    (1 << long(10), 'kiB'),
    (1, 'bytes')
)


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


def does_external_program_run(prog, options):
    """test to see if the external programs can be run"""
    try:
        null = open('/dev/null')
        subprocess.call([prog, '-h'], stdout=null, stderr=null)
        result = True
    except OSError:
        if options.verbose:
            print("couldn't run %s" % prog)
        result = False

    return result


def program_reqs(options):
    """run the external program tester on the required binaries"""
    for program_name in PROGRAMS:
        val = getattr(options, program_name) \
            and does_external_program_run(program_name, options)
        setattr(options, program_name, val)

    do_png = options.optipng or options.pngout or options.advpng
    do_jpeg = options.jpegrescan or options.jpegtran

    do_comics = options.comics

    if not do_png and not do_jpeg and not do_comics:
        print("All optimizers are not available or disabled.")
        exit(1)


def get_options_and_arguments():
    """parses the command line"""
    usage = "%prog [options] [image files]\n"
    usage += "version %s\n" % __version__
    usage += "Uses optiping, pngout, gifsicle, jpegrescan and " \
             "jpegtran if they are on the path."
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-d", "--dir", action="store", dest="dir",
                      default=os.getcwd(),
                      help="Directory to change to before optimiziaton")
    parser.add_option("-f", "--formats", action="store", dest="formats",
                      default=DEFAULT_FORMATS,
                      help="Only optimize images of the specifed '"
                           + FORMAT_DELIMETER + "' delimited formats")
    parser.add_option("-r", "--recurse", action="store_true",
                      dest="recurse", default=0,
                      help="Recurse down through directories ignoring the"
                           "image file arguments on the command line")
    parser.add_option("-q", "--quiet", action="store_false",
                      dest="verbose", default=1,
                      help="Do not display output")
    parser.add_option("-o", "--disable_optipng", action="store_false",
                      dest="optipng", default=1,
                      help="Do not optimize with optipng")
    parser.add_option("-a", "--enable_advpng", action="store_true",
                      dest="advpng", default=0,
                      help="Optimize with advpng (disabled by default)")
    parser.add_option("-p", "--disable_pngout", action="store_false",
                      dest="pngout", default=1,
                      help="Do not optimize with pngout")
    parser.add_option("-j", "--disable_jpegrescan", action="store_false",
                      dest="jpegrescan", default=1,
                      help="Do not optimize with jpegrescan")
    parser.add_option("-e", "--disable_progressive", action="store_false",
                      dest="jpegtran_prog", default=1,
                      help="Don't try to reduce size by making "
                      "progressive JPEGs with jpegtran")
    parser.add_option("-t", "--disable_jpegtran", action="store_false",
                      dest="jpegtran", default=1,
                      help="Do not optimize with jpegtran")
    parser.add_option("-b", "--bigger", action="store_true",
                      dest="bigger", default=0,
                      help="Save optimized files that are larger than "
                           "the originals")
    parser.add_option("-n", "--noop", action="store_true",
                      dest="test", default=0,
                      help="Do not replace files with optimized versions")
    parser.add_option("-l", "--list", action="store_true",
                      dest="list_only", default=0,
                      help="Only list files that would be optimized")
    parser.add_option("-c", "--comics", action="store_true",
                      dest="comics", default=0,
                      help="Also optimize comic book archives (cbz & cbr)")
    parser.add_option("-g", "--disable_gifsicle", action="store_false",
                      dest="gifsicle", default=1,
                      help="disable optimizing animated GIFs")
    parser.add_option("-C", "--disable_convert_type", action="store_false",
                      dest="convert_types", default=1,
                      help="Do not convert other lossless formats like "
                           "GIFs and TIFFs to PNGs when optimizing")
    parser.add_option("-S", "--disable_follow_symlinks", action="store_false",
                      dest="follow_symlinks", default=1,
                      help="disable following symlinks for files and "
                           "directories")
    parser.add_option("-D", "--optimize_after", action="store",
                      dest="optimize_after", default=None,
                      help="only optimize files after the specified "
                           "timestamp. Supercedes -T")
    parser.add_option("-T", "--record_timestamp", action="store_true",
                      dest="record_timestamp", default=0,
                      help="Store the time of the optimization of full "
                           "directories in directory local dotfiles.")
    parser.add_option("-v", "--version", action="store_true",
                      dest="version", default=0,
                      help="display the version number")

    (options, arguments) = parser.parse_args()

    if options.version:
        print('version', __version__)
        exit(0)

    if len(arguments) == 0:
        parser.print_help()
        exit(1)

    program_reqs(options)

    if options.convert_types:
        options.to_png_formats = PNG_CONVERTABLE_FORMATS
    else:
        options.to_png_formats = PNG_FORMATS

    if options.formats == DEFAULT_FORMATS:
        options.formats = options.to_png_formats | JPEG_FORMATS | \
                          COMIC_FORMATS | GIF_FORMATS
    else:
        options.formats = options.formats.split(FORMAT_DELIMETER)

    if options.optimize_after is not None:
        try:
            after_dt = dateutil.parser.parse(options.optimize_after)
            options.optimize_after = time.mktime(after_dt.timetuple())
        except Exception as ex:
            print(ex)
            print('Could not parse date to optimize after.')
            exit(1)

    arguments.sort()

    return (options, arguments)


def replace_ext(filename, new_ext):
    """replaces the file extention"""
    filename_base = os.path.splitext(filename)[0]
    new_filename = '{}.{}'.format(filename_base, new_ext)
    return new_filename


def new_percent_saved(size_in, size_out):
    """spits out how much space the optimazation saved"""
    percent_saved = (1 - (size_out / size_in)) * 100

    size_saved_kb = humanize_bytes(size_in - size_out)
    result = '%.*f%s (%s)' % (2, percent_saved, '%', size_saved_kb)
    return result


def run_ext(args):
    """run EXTERNAL program"""
    subprocess.call(args, stdout=subprocess.PIPE)


def pngout(filename, new_filename):
    """runs the EXTERNAL program pngout on the file"""
    args = PNGOUT_ARGS + [filename, new_filename]
    run_ext(args)


def optipng(filename, new_filename):
    """runs the EXTERNAL program optipng on the file"""
    args = OPTIPNG_ARGS + [new_filename]
    run_ext(args)


def advpng(filename, new_filename):
    """runs the EXTERNAL program advpng on the file"""
    args = ADVPNG_ARGS + [new_filename]
    run_ext(args)


def gifsicle(filename, new_filename):
    """runs the EXTERNAL program gifsicle"""
    args = GIFSICLE_ARGS + [new_filename]
    run_ext(args)


def jpegtranopti(filename, new_filename):
    """runs the EXTERNAL program jpegtran with huffman optimization
       on the file"""
    args = JPEGTRAN_OPTI_ARGS + [new_filename, filename]
    run_ext(args)


def jpegtranprog(filename, new_filename):
    """runs the EXTERNAL program jpegtran with progressive transform
       on the file"""
    args = JPEGTRAN_PROG_ARGS + [new_filename, filename]
    run_ext(args)


def jpegrescan(filename, new_filename):
    """runs the EXTERNAL program jpegrescan"""
    args = JPEGRESCAN_ARGS + [filename, new_filename]
    run_ext(args)


def is_format_selected(image_format, formats, options, mode):
    """returns a boolean indicating weather or not the image format
    was selected by the command line options"""
    intersection = formats & options.formats
    result = (image_format in intersection) and mode
    return result


def cleanup_after_optimize(filename, new_filename, options):
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
                                   or options.bigger):
            old_image_format = get_image_format(filename)
            new_image_format = get_image_format(new_filename)
            if old_image_format != new_image_format:
                final_filename = replace_ext(filename,
                                             new_image_format.lower())
            rem_filename = filename + REMOVE_EXT
            if not options.test:
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

    return bytes_diff, final_filename


def optimize_image_external(filename, options, func):
    """this could be a decorator"""
    new_filename = os.path.normpath(filename + NEW_EXT)
    shutil.copy2(filename, new_filename)

    func(filename, new_filename)

    bytes_diff, final_filename = cleanup_after_optimize(filename,
                                                        new_filename,
                                                        options)
    percent = new_percent_saved(bytes_diff['in'], bytes_diff['out'])
    if percent != 0:
        report = '%s: %s' % (func.__name__, percent)
    else:
        report = ''
    return (bytes_diff, report, final_filename)


def optimize_gif(filename, options):
    """run EXTERNAL programs to optimize animated gifs"""
    if options.gifsicle:
        bytes_diff, rep, final_filename = optimize_image_external(
            filename, options, gifsicle)
    else:
        rep = ['Skipping animated GIF: %s' % filename]
        bytes_diff = {'in': 0, 'out': 0}

    report_list = [rep]

    return bytes_diff, report_list, final_filename


def optimize_png(filename, options):
    """run EXTERNAL programs to optimize lossless formats to PNGs"""
    bytes_diff = None
    report_list = []
    final_filename = filename

    filesize_in = os.stat(filename).st_size

    for ext_prog in ('optipng', 'advpng', 'pngout'):
        if not getattr(options, ext_prog) :
            continue
        bytes_diff, rep, final_filename = optimize_image_external(
            final_filename, options, globals()[ext_prog])
        if rep:
            report_list += [rep]

    if bytes_diff is not None:
        bytes_diff['in'] = filesize_in
    else:
        report_list += ['Skipping PNG file: %s' % final_filename]
        bytes_diff = {'in': 0, 'out': 0}

    return bytes_diff, report_list, final_filename


def optimize_jpeg(filename, options):
    """run EXTERNAL programs to optimize jpeg formats"""
    final_filename = filename
    if options.jpegrescan:
        bytes_diff, rep, final_filename = optimize_image_external(
            final_filename, options, jpegrescan)
    elif options.jpegtran_prog:
        bytes_diff, rep, final_filename = optimize_image_external(
            final_filename, options, jpegtranprog)
    elif options.jpegtran:
        bytes_diff, rep, final_filename = optimize_image_external(
            final_filename, options, jpegtranopti)
    else:
        rep = ['Skipping JPEG file: %s' % filename]
        bytes_diff = {'in': 0, 'out': 0}

    report_list = [rep]

    return bytes_diff, report_list, final_filename


def optimize_image(arg):
    """optimizes a given image from a filename"""
    try:
        filename, image_format, options, total_bytes_in, total_bytes_out = arg

        #print(filename, image_format, "starting...")

        if is_format_selected(image_format, options.to_png_formats,
                              options, options.optipng or options.pngout):
            bytes_diff, report_list, final_filename = optimize_png(
                filename, options)
        elif is_format_selected(image_format, JPEG_FORMATS, options,
                                options.jpegrescan or options.jpegtran):
            bytes_diff, report_list, final_filename = optimize_jpeg(
                filename, options)
        elif is_format_selected(image_format, GIF_FORMATS, options,
                                options.gifsicle):
            # this captures still GIFs too if not caught above
            bytes_diff, report_list, final_filename = optimize_gif(
                filename, options)

        else:
            if options.verbose:
                print(filename, image_format)  # image.mode)
                print("\tFile format not selected.")
            return

        optimize_accounting(final_filename, bytes_diff, report_list,
                            total_bytes_in, total_bytes_out, options)
    except Exception as exc:
        print(exc)
        traceback.print_exc(exc)
        raise exc


def optimize_accounting(filename, bytes_diff, report_list, total_bytes_in,
                        total_bytes_out, options):
    """record the percent saved, print it and add it to the totals"""
    report = filename + ': '
    total = new_percent_saved(bytes_diff['in'], bytes_diff['out'])
    if total:
        report += total
    else:
        report += '0%'
    if options.test:
        report += ' could be saved.'
    tools_report = ', '.join(report_list)
    if tools_report:
        report += '\n\t' + tools_report

    total_bytes_in.set(total_bytes_in.get() + bytes_diff['in'])
    total_bytes_out.set(total_bytes_out.get() + bytes_diff['out'])

    print(report)


def is_image_sequenced(image):
    """determines if the image is a sequenced image"""
    try:
        image.seek(1)
        result = True
    except EOFError:
        result = False

    return result


def get_image_format(filename):
    """gets the image format"""
    image = None
    bad_image = 1
    image_format = 'NONE'
    sequenced = False
    try:
        image = Image.open(filename)
        bad_image = image.verify()
        image_format = image.format
        sequenced = is_image_sequenced(image)
    except (OSError, IOError):
        pass

    if sequenced:
        image_format = SEQUENCED_TEMPLATE % image_format
    elif image is None or bad_image or image_format == 'NONE':
        image_format = 'ERROR'
        filename_ext = os.path.splitext(filename)[-1].lower()
        if filename_ext in COMIC_EXTS:
            if zipfile.is_zipfile(filename):
                image_format = CBZ_FORMAT
            elif rarfile.is_rarfile(filename):
                image_format = CBR_FORMAT
        #TODO levels of verbosity
#        if image_format == 'ERROR' and options.verbose and \
#                not options.list_only:
#            print(filename, "doesn't look like an image or comic archive.")
    return image_format


def detect_file(filename, options):
    """decides what to do with the file"""
    image_format = get_image_format(filename)

    if image_format in options.formats:
        return image_format

    if image_format in ('NONE', 'ERROR'):
        return

    if options.verbose and not options.list_only:
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
        filename, total_bytes_in, total_bytes_out, options = args

        tmp_dir = get_archive_tmp_dir(filename)

        #archive into new filename
        new_filename = replace_ext(filename, NEW_ARCHIVE_SUFFIX)

        print('Rezipping archive', end='')
        with zipfile.ZipFile(new_filename, 'w',
                             compression=zipfile.ZIP_DEFLATED) as new_zf:
            root_len = len(os.path.abspath(tmp_dir))
            for root, dirs, files in os.walk(tmp_dir):
                archive_root = os.path.abspath(root)[root_len:]
                for fname in files:
                    fullpath = os.path.join(root, fname)
                    archive_name = os.path.join(archive_root, fname)
                    print('.', end='')
                    new_zf.write(fullpath, archive_name, zipfile.ZIP_DEFLATED)

        # Cleanup tmpdir
        if os.path.isdir(tmp_dir):
            print('.', end='')
            shutil.rmtree(tmp_dir)
        print('done.')

        bytes_diff, final_filename = cleanup_after_optimize(filename,
                                                            new_filename,
                                                            options)

        optimize_accounting(final_filename, bytes_diff, [''],
                            total_bytes_in, total_bytes_out, options)
    except Exception as exc:
        print(exc)
        traceback.print_exc(exc)
        raise exc


def comic_archive_uncompress(filename, image_format, options):
    """ uncompress comic archives and return the name of the working
        directory we uncompressed into """

    if not options.comics:
        report = ['Skipping archive file: %s' % filename]
        report_list = [report]
        bytes_diff = {'in': 0, 'out': 0}
        return (bytes_diff, report_list)

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

    return os.path.basename(tmp_dir)


def get_timestamp(dirname_full, remove, options):
    """ get the timestamp from the timestamp file and optionally remove it
        if we're going to write another one.
    """
    record_filename = os.path.join(dirname_full, RECORD_FILENAME)

    if os.path.exists(record_filename):
        mtime = os.stat(record_filename).st_mtime
        if options.record_timestamp and remove:
            os.remove(record_filename)
        return mtime

    return None


def get_parent_timestamp(full_pathname, mtime, options):
    """ get the timestamps up the directory tree because they affect
        every subdirectory """
    parent_pathname = os.path.dirname(full_pathname)

    mtime = max(get_timestamp(parent_pathname, False, options), mtime)

    if parent_pathname == os.path.dirname(parent_pathname):
        return mtime

    return get_parent_timestamp(parent_pathname, mtime, options)


def record_timestamp(pathname_full, options):
    """Record the timestamp of running in a dotfile"""
    if options.test or options.list_only or not options.record_timestamp:
        return
    elif not options.follow_symlinks and os.path.islink(pathname_full):
        return
    elif not os.path.isdir(pathname_full):
        return

    record_filename_full = os.path.join(pathname_full, RECORD_FILENAME)
    try:
        with open(record_filename_full, 'w'):
            os.utime(record_filename_full, None)
    except IOError:
        print("Could not set timestamp in %s" % pathname_full)

def get_optimize_after(current_path, look_up, optimize_after, options):
    """ Figure out the which mtime to check against and if we look up
        return that we've looked up too"""
    if options.optimize_after is not None:
        optimize_after = options.optimize_after
    else:
        if look_up:
            optimize_after = get_parent_timestamp(current_path,
                                                  optimize_after,
                                                  options)
        optimize_after = max(get_timestamp(current_path, True, options),
                             optimize_after)
    return optimize_after


def optimize_dir(filename_full, options, multiproc, optimize_after):
    """ Recursively optimize a directory """
    if not options.recurse:
        return
    next_dir_list = os.listdir(filename_full)
    next_dir_list.sort()
    optimize_after = get_optimize_after(filename_full, False,
                                        optimize_after, options)
    optimize_files(filename_full, next_dir_list, options, multiproc,
                   optimize_after)


def optimize_comic_archive(filename_full, image_format, options, multiproc,
                          optimize_after):
    """ Optimize a comic archive """
    tmp_dir_basename = comic_archive_uncompress(filename_full,
                                                image_format, options)
    # recurse into comic archive even if flag not set
    if options.recurse:
        archive_options = options
    else:
        archive_options = copy.deepcopy(options)
        archive_options.recurse = True

    # optimize contents of comic archive
    dirname = os.path.dirname(filename_full)
    optimize_files(dirname, [tmp_dir_basename], archive_options,
                   multiproc, optimize_after)

    # XXX hackish
    # closing and recreating the pool for every dir
    # is not ideal but it lets me make sure all files
    # are done optimizing before i apply timestamps or
    # recompress
    old_pool = multiproc['pool']
    old_pool.close()
    old_pool.join()

    new_pool = multiprocessing.Pool()
    multiproc['pool'] = new_pool

    args = (filename_full, multiproc['in'],
            multiproc['out'], options)
    new_pool.apply_async(comic_archive_compress,
                            args=(args,))


def optimize_file(filename_full, options, multiproc, optimize_after):
    """ Optimize an individual file """
    if optimize_after is not None:
        mtime = os.stat(filename_full).st_mtime
        if mtime <= optimize_after:
            return

    image_format = detect_file(filename_full, options)
    if not image_format:
        return

    if options.list_only:
        # list only
        print("%s : %s" % (filename_full, image_format))
    elif is_format_selected(image_format, COMIC_FORMATS,
                            options, options.comics):
        optimize_comic_archive(filename_full, image_format, options,
                               multiproc, optimize_after)
    else:
        # regular image
        args = [filename_full, image_format, options,
                multiproc['in'], multiproc['out']]
        multiproc['pool'].apply_async(optimize_image, args=(args,))


def optimize_files(cwd, filter_list, options, multiproc, optimize_after):
    """sorts through a list of files, decends directories and
       calls the optimizer on the extant files"""

    for filename in filter_list:

        filename_full = os.path.join(cwd, filename)
        filename_full = os.path.normpath(filename_full)

        if not options.follow_symlinks and os.path.islink(filename_full):
            continue
        elif os.path.basename(filename_full) == RECORD_FILENAME:
            continue
        elif os.path.isdir(filename_full):
            optimize_dir(filename_full, options, multiproc,
                         optimize_after)
        elif os.path.exists(filename_full):
            optimize_file(filename_full, options, multiproc,
                          optimize_after)
        elif options.verbose:
            print(filename_full, 'was not found.')


def report_totals(bytes_in, bytes_out, options):
    """report the total number and percent of bytes saved"""
    if bytes_in:
        bytes_saved = bytes_in - bytes_out
        percent_bytes_saved = bytes_saved / bytes_in * 100
        msg = ''
        if options.test:
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
        print(msg)
        if options.test:
            print("Test run did not change any files.")

    else:
        print("Didn't optimize any files.")


def main():
    """main"""
    #TODO make the relevant parts of this call as a library


    # Init
    ImageFile.MAXBLOCK = 3000000  # default is 64k

    (options, arguments) = get_options_and_arguments()

    os.chdir(options.dir)
    cwd = os.getcwd()
    filter_list = set(arguments)

    manager = multiprocessing.Manager()
    total_bytes_in = manager.Value(int, 0)
    total_bytes_out = manager.Value(int, 0)
    pool = multiprocessing.Pool()

    multiproc = {'pool': pool, 'in': total_bytes_in, 'out': total_bytes_out}
    record_dirs = set()
    cwd_files = set()

    # Optimize
    for filename in filter_list:

        if options.recurse and os.path.isdir(filename):
            # dirs to put timestamps in later
            record_dirs.add(filename)

        if os.path.isabs(filename):
            # optimize absolute paths on the command line
            abs_dir = os.path.dirname(filename)
            optimize_after = get_optimize_after(abs_dir, True, None,
                                                options)
            optimize_files(abs_dir, [filename], options, multiproc,
                           optimize_after)
        else:
            cwd_files.add(filename)

    if len(cwd_files):
        # optimize cwd files
        optimize_after = get_optimize_after(cwd, True, None, options)
        optimize_files(cwd, cwd_files, options, multiproc, optimize_after)


    pool = multiproc['pool']
    pool.close()
    pool.join()

    # Finish up
    for filename in record_dirs:
        record_timestamp(filename, options)

    report_totals(multiproc['in'].get(), multiproc['out'].get(), options)


if __name__ == '__main__':
    main()
