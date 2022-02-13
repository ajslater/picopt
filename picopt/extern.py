"""Run external programs."""
import subprocess

from typing import Tuple


class ExtArgs:
    """Arguments for external programs."""

    def __init__(
        self, old_path: str, new_path: str, image_format: str, destroy_metadata: bool
    ) -> None:
        """Set arguments."""
        self.old_fn: str = old_path
        self.new_fn: str = new_path
        self.image_format: str = image_format
        self.destroy_metadata: bool = destroy_metadata


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
