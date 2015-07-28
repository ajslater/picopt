from __future__ import division
import subprocess

from settings import Settings


def does_external_program_run(prog):
    """test to see if the external programs can be run"""
    try:
        null = open('/dev/null')
        subprocess.call([prog, '-h'], stdout=null, stderr=null)
        result = True
    except OSError:
        if Settings.verbose > 1:
            print("couldn't run %s" % prog)
        result = False

    return result


def program_reqs(PROGRAMS):
    """run the external program tester on the required binaries"""
    for program in PROGRAMS:
        val = getattr(Settings, program.__name__) \
            and does_external_program_run(program.__name__)
        setattr(Settings, program.__name__, val)

    do_png = Settings.optipng or Settings.pngout or Settings.advpng
    do_jpeg = Settings.mozjpeg or Settings.jpegrescan or Settings.jpegtran

    do_comics = Settings.comics

    if not do_png and not do_jpeg and not do_comics:
        print("All optimizers are not available or disabled.")
        exit(1)


def run_ext(args):
    """run EXTERNAL program"""
    subprocess.call(args, stdout=subprocess.PIPE)
