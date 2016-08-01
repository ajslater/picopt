"""Run external programs."""
from __future__ import print_function
from __future__ import division
import subprocess

from .settings import Settings


def does_external_program_run(prog):
    """Test to see if the external programs can be run."""
    try:
        null = open('/dev/null')
        subprocess.call([prog, '-h'], stdout=null, stderr=null)
        result = True
    except OSError:
        if Settings.verbose > 1:
            print("couldn't run %s" % prog)
        result = False

    return result


def run_ext(args):
    """Run EXTERNAL program."""
    subprocess.call(args, stdout=subprocess.PIPE)
