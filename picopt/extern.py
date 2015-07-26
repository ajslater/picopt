from collections import namedtuple
import os
import shutil
import subprocess

import file_format
import stats


REMOVE_EXT = '.%s-remove' % PROGRAM_NAME
NEW_EXT = '.%s-optimized.png' % PROGRAM_NAME


ExtArgs = namedtuple('ExtArgs', ['old_filename', 'new_filename', 'arguments'])


# C
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


def program_reqs(arguments, programs):
    """run the external program tester on the required binaries"""
    for program_name in programs:
        val = getattr(arguments, program_name) \
            and does_external_program_run(program_name, arguments)
        setattr(arguments, program_name, val)

    do_png = arguments.optipng or arguments.pngout or arguments.advpng
    do_jpeg = arguments.mozjpeg or arguments.jpegrescan or arguments.jpegtran

    do_comics = arguments.comics

    if not do_png and not do_jpeg and not do_comics:
        print("All optimizers are not available or disabled.")
        exit(1)


# B
def run_ext(args):
    """run EXTERNAL program"""
    subprocess.call(args, stdout=subprocess.PIPE)


# A
def replace_ext(filename, new_ext):
    """replaces the file extention"""
    filename_base = os.path.splitext(filename)[0]
    new_filename = '{}.{}'.format(filename_base, new_ext)
    return new_filename


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
        if (filesize_out > 0) and ((filesize_out < filesize_in) or
                                   arguments.bigger):
            old_image_format = file_format.get_image_format(filename,
                                                            arguments)
            new_image_format = file_format.get_image_format(new_filename,
                                                            arguments)
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

    return stats.ReportStats._make([final_filename, bytes_diff, []])


def optimize_image_external(filename, arguments, func):
    """this could be a decorator"""
    new_filename = os.path.normpath(filename + NEW_EXT)
    shutil.copy2(filename, new_filename)

    ext_args = ExtArgs._make([filename, new_filename, arguments])
    func(ext_args)

    report_stats = cleanup_after_optimize(filename, new_filename, arguments)
    percent = stats.new_percent_saved(report_stats)
    if percent != 0:
        report = '%s: %s' % (func.__name__, percent)
    else:
        report = ''
    report_stats.report_list.append(report)

    return report_stats
