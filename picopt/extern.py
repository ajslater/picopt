from __future__ import division
import subprocess


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


def run_ext(args):
    """run EXTERNAL program"""
    subprocess.call(args, stdout=subprocess.PIPE)
