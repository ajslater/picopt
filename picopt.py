#!/usr/bin/env python
"""
Runs pictures through image specific external optimizers
"""
from __future__ import print_function
from __future__ import division

__revision__ = '0.7.0'

import sys
import os
import optparse
import shutil
import subprocess
import Image
import ImageFile
import multiprocessing

REMOVE_EXT = '.picopt-remove'
NEW_EXT = '.picopt-optimized.png'
JPEGTRAN_OPTI_ARGS = ['jpegtran', '-copy', 'all', '-optimize',
                      '-outfile']
JPEGTRAN_PROG_ARGS = ['jpegtran', '-copy', 'all', '-optimize',
                      '-outfile']
JPEGRESCAN_ARGS = ['jpegrescan']
OPTIPNG_ARGS = ['optipng', '-o6', '-fix', '-preserve', '-force', '-quiet']
ADVPNG_ARGS = ['advpng', '-z', '-4', '-f']
PNGOUT_ARGS = ['pngout', '-q', '-force', '-y']
LOSSLESS_FORMATS = ['PNG', 'PNM', 'GIF', 'TIFF']
JPEG_FORMATS = ['JPEG']
OPTIMIZABLE_FORMATS = LOSSLESS_FORMATS + JPEG_FORMATS
FORMAT_DELIMETER = ','
DEFAULT_FORMATS = 'ALL'
PROCESSES = multiprocessing.cpu_count() + 1

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


def does_external_program_run(prog):
    """test to see if the external programs can be run"""
    try:
        null = open('/dev/null')
        subprocess.call([prog, '-h'], stdout=null, stderr=null)
        result = True
    except OSError:
        print("couldn't run %s" % prog)
        result = False

    return result


def program_reqs(options):
    """run the external program tester on the required binaries"""
    options.optipng = options.optipng and does_external_program_run('optipng')
    options.advpng = options.advpng and does_external_program_run('advpng')
    options.pngout = options.pngout and does_external_program_run('pngout')
    lossless = options.optipng or options.advpng or options.pngout

    options.jpegrescan = options.jpegtran and \
                         does_external_program_run('jpegrescan')
    options.jpegtran = options.jpegtran and \
                       does_external_program_run('jpegtran')

    lossy = options.jpegrescan or options.jpegtran

    if not lossless and not lossy:
        print("All optimizers are not available or disabled.")
        exit(1)


def get_options_and_arguments():
    """parses the command line"""
    usage = "usage: %prog [options] [image files]\npicopt uses " \
    "optiping, advpng, pngout, jpegrescan and jpegtran be if they are " \
    "on the path."
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-d", "--dir", action="store", dest="dir",
        default=os.getcwd(),
    help="Directory to change to before optimiziaton")
    parser.add_option("-f", "--formats", action="store", dest="formats",
        default=DEFAULT_FORMATS,
    help="Only optimize images of the specifed '"
            + FORMAT_DELIMETER + "' delimited formats")
    parser.add_option("-r", "--recurse", action="store_true",
        dest="recurse", default=0, help="Recurse down through "
            "directories ignoring the image file arguments on the "
            "command line")
    parser.add_option("-q", "--quiet", action="store_false",
        dest="verbose", default=1, help="Do not display output")
    parser.add_option("-o", "--disable_optipng", action="store_false",
        dest="optipng", default=1, help="Do not optimize with optipng")
    parser.add_option("-a", "--disable_advpng", action="store_false",
        dest="advpng", default=1, help="Do not optimize with advpng")
    parser.add_option("-p", "--disable_pngout", action="store_false",
        dest="pngout", default=1, help="Do not optimize with pngout")
    parser.add_option("-j", "--disable_jpegrescan", action="store_false",
        dest="jpegrescan", default=1, help="Do not optimize with jpegrescan")
    parser.add_option("-g", "--disable_progressive", action="store_false",
        dest="jpegtran_prog", default=1,
        help="Don't try to reduce size by making progressive JPEGs with "
             "jpegtran")
    parser.add_option("-t", "--disable_jpegtran", action="store_false",
        dest="jpegtran", default=1, help="Do not optimize with jpegscan")
    parser.add_option("-b", "--bigger", action="store_true",
        dest="bigger", default=0,
        help="Save optimized files that are larger than the originals")

    (options, arguments) = parser.parse_args()

    if len(arguments) == 0:
        parser.print_help()
        exit(1)

    program_reqs(options)

    if options.formats == DEFAULT_FORMATS:
        options.formats = OPTIMIZABLE_FORMATS
    else:
        options.formats = options.formats.split(FORMAT_DELIMETER)
    arguments.sort()

    return (options, arguments)


def replace_ext(filename, new_ext):
    """replaces the file extention"""
    filename_base, old_ext = os.path.splitext(filename)
    new_filename = '{}.{}'.format(filename_base, new_ext)
    return new_filename


def new_percent_saved(size_in, size_out):
    """spits out how much space the optimazation saved"""
    percent_saved = (1 - (size_out / size_in)) * 100
    if percent_saved <= 0:
        return ''

    size_saved_kb = humanize_bytes(size_in - size_out)
    result = '%.*f%s (%s)' % (2, percent_saved, '%', size_saved_kb)
    return result


#def report_percent_saved(size_in, size_out):
#    """spits out how much space the optimazation saved"""
#    size_in_kb = humanize_bytes(size_in)
#    size_out_kb = humanize_bytes(size_out)
#    result = '\t' + size_in_kb + '-->' + size_out_kb + '. '
#
#    percent_saved = (1 - (size_out / size_in)) * 100
#
#    if percent_saved == 0:
#        result += 'Files are the same size. '
#    else:
#        if percent_saved > 0:
#            verb = 'Shrunk'
#        else:
#            verb = 'Grew'
#
#        bytes_saved = humanize_bytes(abs(size_in - size_out))
#        result += verb + ' by %.*f%s' % (2, abs(percent_saved), '%')
#        result += ' or %s. ' % bytes_saved
#
#    return result


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
    result = (image_format in formats) and \
             (image_format in options.formats) and mode
    return result


def cleanup_after_optimize(filename, new_filename, options):
    """report results. replace old file with better one or discard new wasteful
       file"""

    bytes_diff = {'in': 0, 'out': 0}
    try:
        filesize_in = os.stat(filename).st_size
        bytes_diff['in'] = filesize_in
        bytes_diff['out'] = filesize_in  # overwritten on succes below
        filesize_out = os.stat(new_filename).st_size

        if (filesize_out > 0) and ((filesize_out < filesize_in)
                                   or options.bigger):
            old_image_format = get_image_format(filename)
            new_image_format = get_image_format(new_filename)
            if old_image_format == new_image_format:
                final_filename = filename
            else:
                final_filename = replace_ext(filename,
                                             new_image_format.lower())
            rem_filename = filename + REMOVE_EXT
            os.rename(filename, rem_filename)
            os.rename(new_filename, final_filename)
            os.remove(rem_filename)
            bytes_diff['out'] = filesize_out  # only on completion
        else:
            os.remove(new_filename)
    except OSError as ex:
        print(ex)

    return bytes_diff


def optimize_image_aux(filename, options, func):
    """this could be a decorator"""
    new_filename = os.path.normpath(filename + NEW_EXT)
    shutil.copy2(filename, new_filename)

    func(filename, new_filename)

    bytes_diff = cleanup_after_optimize(filename, new_filename, options)
    percent = new_percent_saved(bytes_diff['in'], bytes_diff['out'])
    if percent:
        report = '%s: %s' % (func.__name__, percent)
    else:
        report = ''
    return (bytes_diff, report)


def lossless(filename, options):
    """run EXTERNAL programs to optimize lossless formats"""
    bytes_in = 0
    report_list = []
    if options.optipng:
        bytes_diff, rep = optimize_image_aux(filename, options, optipng)
        if rep:
            report_list += [rep]
        if not bytes_in:
            bytes_in = bytes_diff['in']

    if options.advpng:
        bytes_diff, rep = optimize_image_aux(filename, options, advpng)
        if rep:
            report_list += [rep]
        if not bytes_in:
            bytes_in = bytes_diff['in']

    if options.pngout:
        bytes_diff, rep = optimize_image_aux(filename, options, pngout)
        if rep:
            report_list += [rep]
        if not bytes_in:
            bytes_in = bytes_diff['in']

    if not bytes_in:
        print('Skipping lossless file: %s', filename)
        bytes_diff = {'in': 0, 'out': 0}

    bytes_diff['in'] = bytes_in

    return bytes_diff, report_list


def lossy(filename, options):
    """run EXTERNAL programs to optimize lossy formats"""
    if options.jpegrescan:
        bytes_diff, rep = optimize_image_aux(filename, options, jpegrescan)
    elif options.jpegtran_prog:
        bytes_diff, rep = optimize_image_aux(filename, options, jpegtranprog)
    elif options.jpegtran:
        bytes_diff, rep = optimize_image_aux(filename, options, jpegtranopti)
    else:
        print('Skipping jpeg file: %s', filename)
        bytes_diff = {'in': 0, 'out': 0}

    report_list = [rep]

    return bytes_diff, report_list


def optimize_image(arg):
    """optimizes a given image from a filename"""
    filename, image_format, options, total_bytes_in, total_bytes_out = arg

    #print(filename, image_format, "starting...")

    if is_format_selected(image_format, LOSSLESS_FORMATS, options,
                          options.optipng or options.pngout):
        bytes_diff, report_list = lossless(filename, options)
    elif is_format_selected(image_format, JPEG_FORMATS, options,
                            options.jpegrescan or options.jpegtran):
        bytes_diff, report_list = lossy(filename, options)
    else:
        if options.verbose:
            print(filename, image_format)  # image.mode)
            print("\tFile format not selected.")

    report = filename + ': '
    total = new_percent_saved(bytes_diff['in'], bytes_diff['out'])
    if total:
        report += total
    else:
        report += '0%'
    tools_report = ', '.join(report_list)
    if tools_report:
        report += '\n\t' + tools_report
    print(report)

    total_bytes_in.set(total_bytes_in.get() + bytes_diff['in'])
    total_bytes_out.set(total_bytes_out.get() + bytes_diff['out'])


def is_image_sequenced(image):
    """determines if the image is a sequenced image"""
    try:
        image.seek(1)
        result = 1
    except EOFError:
        result = 0

    return result


def get_image_format(filename):
    """gets the image format"""
    image = None
    bad_image = 1
    image_format = 'NONE'
    sequenced = 0
    try:
        image = Image.open(filename)
        bad_image = image.verify()
        image_format = image.format
        sequenced = is_image_sequenced(image)
    except (OSError, IOError):
        pass

    if sequenced:
        print (filename, "can't handle sequenced image")
        image_format += ' SEQUENCED'
    elif image is None or bad_image or image_format == 'NONE':
        print(filename, "doesn't look like an image.")
        image_format = 'ERROR'
    return image_format


def detect_file(filename, options):
    """decides what to do with the file"""
    image_format = get_image_format(filename)

    if image_format in options.formats:
        return [filename, image_format]
        #print(filename, image_format)  # image.mode)
        #optimize_image(filename, image_format, options, totals)
    elif image_format in ('NONE', 'ERROR'):
        pass
    else:
        print(filename, image_format, 'is not a supported image type.')


def optimize_files(cwd, filter_list, options, multiproc):
    """sorts through a list of files, decends directories and
       calls the optimizer on the extant files"""

    for filename in filter_list:
        filename_full = os.path.normpath(cwd + os.sep + filename)
        if os.path.isdir(filename_full):
            if options.recurse:
                next_dir_list = os.listdir(filename_full)
                next_dir_list.sort()
                optimize_files(filename_full, next_dir_list, options,
                               multiproc)
        elif os.path.exists(filename_full):
            args = detect_file(filename_full, options)
            if args:
                #print("Queueing", *args)
                args += [options, multiproc['in'], multiproc['out']]
                multiproc['pool'].apply_async(optimize_image, [args])
        else:
            if options.verbose:
                print(filename, 'was not found.')


def report_totals(bytes_in, bytes_out):
    """report the total number and percent of bytes saved"""
    if bytes_in:
        bytes_saved = bytes_in - bytes_out
        percent_bytes_saved = bytes_saved / bytes_in * 100
        print("Saved %s or %.*f%s" % (humanize_bytes(bytes_saved), 2,
                                      percent_bytes_saved, '%'))
    else:
        print("Didn't optimize any files.")


def main():
    """main"""

    ImageFile.MAXBLOCK = 3000000  # default is 64k

    (options, arguments) = get_options_and_arguments()

    os.chdir(options.dir)
    cwd = os.getcwd()
    filter_list = arguments

    manager = multiprocessing.Manager()
    total_bytes_in = manager.Value(int, 0)
    total_bytes_out = manager.Value(int, 0)
    pool = multiprocessing.Pool(processes=PROCESSES)

    multiproc = {'pool': pool, 'in': total_bytes_in, 'out': total_bytes_out}

    optimize_files(cwd, filter_list, options, multiproc)

    pool.close()
    pool.join()

    report_totals(total_bytes_in.get(), total_bytes_out.get())


if __name__ == '__main__':
    main()
