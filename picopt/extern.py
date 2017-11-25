"""Run external programs."""
from __future__ import absolute_import, division, print_function

import subprocess


class ExtArgs(object):
    """Arguments for external programs."""

    def __init__(self, old_filename, new_filename):
        """Set arguments."""
        self.old_filename = old_filename
        self.new_filename = new_filename


def does_external_program_run(prog, verbose):
    """Test to see if the external programs can be run."""
    try:
        with open('/dev/null') as null:
            subprocess.call([prog, '-h'], stdout=null, stderr=null)
        result = True
    except OSError:
        if verbose > 1:
            print("couldn't run {}".format(prog))
        result = False

    return result


def run_ext(args):
    """Run EXTERNAL program."""
    subprocess.check_call(args, stdout=subprocess.PIPE)
