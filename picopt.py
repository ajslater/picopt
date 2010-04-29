#!/usr/bin/env python
"""
Runs pictures through image specific external optimizers
"""
from __future__ import print_function
from __future__ import division

__revision__ = '0.2.0'

import sys, os, optparse, shutil, subprocess
import Image, ImageFile

PNG_EXT = '.png'
MNG_EXT = '.mng'
JPEG_EXT = '.jpg'
NEW_EXT = '.picopt-optimized'
JPEGTRAN_ARGS = ['jpegtran', '-perfect', '-copy', 'all', '-optimize',
                 '-outfile']
OPTIPNG_ARGS = ['optipng', '-o7', '-fix', '-preserve', '-force', '-quiet']
DU_ARGS = ['du', '--human-readable', '--summarize']
LOSSLESS_FORMATS = ['PNG', 'PNM', 'GIF', 'TIFF']
JPEG_FORMATS = ['JPEG']
OPTIMIZABLE_FORMATS = LOSSLESS_FORMATS + JPEG_FORMATS
FORMAT_DELIMETER = ','
DEFAULT_FORMATS = 'ALL'

def program_runs(prog) :
    """test to see if the external programs can be run"""
    try :
        null = open('/dev/null')
        subprocess.call([prog, '-h'], stdout=null, stderr=null)
    except OSError:
        print("couldn't run %s" % prog)
        exit(1)
 
def program_reqs() :
    """run the external program tester on the required binaries"""
    program_runs('optipng')
    program_runs('jpegtran')


def get_options_and_arguments() :
    """parses the command line"""
    usage = "usage: %prog [options] [image files]\npicopt requires " \
    "that optiping and jpegtran be on the path."
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-b", "--keepBackup", action="store_true", 
        dest="backup", default=0, 
    help="Keep backup files of the original image")
    parser.add_option("-d", "--dir", action="store", dest="dir", 
        default=os.getcwd(), 
    help="Directory to change to before optimiziaton")
    parser.add_option("-f", "--formats", action="store", dest="formats",
        default=DEFAULT_FORMATS, 
    help="Only optimize images of the specifed '" \
    +FORMAT_DELIMETER+"' delimited formats")
    parser.add_option("-r", "--recurse", action="store_true", 
        dest="recurse", default=0, help="Recurse down through " \
    "directories ignoring the image file arguments on the " \
    "command line")
    parser.add_option("-q", "--quiet", action="store_false", 
        dest="verbose", default=1, help="Do not display output")

    (options, arguments) = parser.parse_args()

    if len(arguments) == 0 :
        parser.print_help()
        exit(1)

    if options.formats == DEFAULT_FORMATS :
        options.formats = OPTIMIZABLE_FORMATS
    else :
        options.formats = options.formats.split(FORMAT_DELIMETER)
    arguments.sort()

    return (options, arguments)


def replace_ext(filename, new_ext) :
    """replaces the file extention"""
    dot_index = filename.rfind('.')
    new_filename = filename[0:dot_index]+new_ext
    return new_filename


def report_percent_saved(size_in, size_out) :
    """spits out how much space the optimazation saved"""
    size_in_kb = str(size_in / 1024)+'kiB'
    size_out_kb = str(size_out / 1024)+'kiB'
    percent_saved = (1 - (float(size_out) / float(size_in))) * 100
  
    if percent_saved == 0 :
        result = 'Files are the same size.'
    else :
        if percent_saved > 0 :
            verb = 'Saved'
        else :
            verb = 'WASTED'
        result = verb+' '+str(percent_saved)

    print(size_in_kb, '-->', size_out_kb+'.', result)



def optipng(filename, new_filename, options) :
    """runs the EXTERNAL program optipng on the file"""
    args = OPTIPNG_ARGS+[new_filename]
    if options.verbose :
        print('\tOptimizing PNG...', end='')
        sys.stdout.flush()
    subprocess.call(args)

    return filename


def jpegtran(filename, new_filename, options) :
    """runs the EXTERNAL program jpegtran on the file"""
    args = JPEGTRAN_ARGS+[new_filename, filename]
    if options.verbose :
        print('\tOptimizing JPEG...', end='')
        sys.stdout.flush()
    subprocess.call(args)
    return filename


def is_format_selected(image_format, formats, options) :
    """returns a boolean indicating weather or not the image format
    was selected by the command line options"""
    result = image_format in formats and image_format in options.formats
    return result

def cleanup_after_optimize(filename, new_filename, options, saved):
    """report results. replace old file with better one or discard new wasteful
       file"""
    try :
        filesize_in = os.stat(filename).st_size
        filesize_out = os.stat(new_filename).st_size
        if options.verbose :
            report_percent_saved(filesize_in, filesize_out)
 
        if (filesize_out > 0) and (filesize_out < filesize_in) :
            print('\tReplacing file with optimized version.')
            rem_filename = filename+'.picopt_REMOVE'
            os.rename(filename, rem_filename)
            os.rename(new_filename, filename)
            os.remove(rem_filename)
            saved['num'] += filesize_in - filesize_out
        else :
            print('\tDiscarding work.')
            os.remove(new_filename)
    except OSError as ex:
        print(ex)


def optimize_image(filename, image_format, options, saved) :
    """optimizes a given image from a filename"""
    new_filename = os.path.normpath(filename+NEW_EXT)
    shutil.copy2(filename, new_filename)

    if is_format_selected(image_format, LOSSLESS_FORMATS, options) :
        optipng(filename, new_filename, options)
    elif is_format_selected(image_format, JPEG_FORMATS, options) :
        jpegtran(filename, new_filename, options)
    else :
        pass

    cleanup_after_optimize(filename, new_filename, options, saved)

def is_image_sequenced(image) :
    """determines if the image is a sequenced image"""
    try :
        image.seek(1)
        result = 1
    except EOFError :
        result = 0

    return result


def detect_file(filename, options, saved) :
    """decides what to do with the file"""
    image = None
    bad_image = 1
    image_format = 'NONE'
    sequenced = 0
    try :
        image = Image.open(filename)
        bad_image = image.verify()
        image_format = image.format
        sequenced = is_image_sequenced(image)
    except (OSError, IOError):
        pass

    if image == None or bad_image or sequenced or image_format == 'NONE' :
        print(filename, "doesn't look like an image.")
    elif image_format in options.formats :
        print(filename, image.format, image.mode)
        optimize_image(filename, image_format, options, saved)
    else :
        print(filename, image.format, 'is not a supported image type.')


def optimize_files(cwd, filter_list, options, saved) :
    """sorts through a list of files, decends directories and
       calls the optimizer on the extant files"""

    for filename in filter_list :
        filename_full = os.path.normpath(cwd+os.sep+filename)
        if os.path.isdir(filename_full) :
            if options.recurse :
                next_dir_list = os.listdir(filename_full)
                next_dir_list.sort()
                optimize_files(filename_full, next_dir_list, options, saved)
        elif os.path.exists(filename_full) :
            detect_file(filename_full, options, saved)
        else :
            if options.verbose :
                print(filename,'was not found.')


def humanize_bytes(num_bytes, precision=1):
    """
    from: 
    http://code.activestate.com/recipes/577081-humanized-representation-of-a-number-of-num_bytes/
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

    abbrevs = (
        (1<<50L, 'PiB'),
        (1<<40L, 'TiB'),
        (1<<30L, 'GiB'),
        (1<<20L, 'MiB'),
        (1<<10L, 'kiB'),
        (1, 'num_bytes')
    )

    if num_bytes == 1:
        return '1 byte'
    for factor, suffix in abbrevs:
        if num_bytes >= factor:
            break
    return '%.*f %s' % (precision, num_bytes / factor, suffix)


def main() :
    """main"""    

    program_reqs()

    ImageFile.MAXBLOCK = 3000000 # default is 64k
    (options, arguments) = get_options_and_arguments()   
 
    os.chdir(options.dir)
    cwd = os.getcwd()
  
    if options.recurse :
        filter_list = os.listdir(cwd)
        filter_list.sort()
    else :
        filter_list = arguments

    saved = { 'num' : 0 }
    optimize_files(cwd, filter_list, options, saved)

    print("Saved %s" % humanize_bytes(saved['num']))


if __name__ == '__main__':
    main()
