"""Run external programs."""
import subprocess

from typing import Tuple


class ExtArgs(object):
    """Arguments for external programs."""

    def __init__(self, old_path: str, new_path: str) -> None:
        """Set arguments."""
        self.old_fn: str = str(old_path)
        self.new_fn: str = str(new_path)


def does_external_program_run(prog: str, verbose: int) -> bool:
    """Test to see if the external programs can be run."""
    try:
        with open("/dev/null") as null:
            subprocess.call([prog, "-h"], stdout=null, stderr=null)
        result = True
    except OSError:
        if verbose > 1:
            print(f"couldn't run {prog}")
        result = False

    return result


def run_ext(args: Tuple[str, ...]) -> None:
    """Run EXTERNAL program."""
    try:
        subprocess.check_call(args)
    except subprocess.CalledProcessError as exc:
        print(exc)
        print(exc.cmd)
        print(exc.returncode)
        print(exc.output)
        raise
