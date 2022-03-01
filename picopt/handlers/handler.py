"""FileType abstract class for image and container formats."""
import subprocess

from abc import ABC
from dataclasses import dataclass
from pathlib import Path
from typing import Set, Tuple

from confuse.templates import AttrDict

from picopt import PROGRAM_NAME


@dataclass(eq=True, frozen=True)
class Format:
    """A file format, with image attributes."""

    format: str
    lossless: bool = True
    animated: bool = False


class Handler(ABC):
    """FileType superclass for image and container formats."""

    BEST_ONLY: bool = True
    FORMAT_STR: str = "unimplemented"
    FORMAT: Format = Format(FORMAT_STR, False, False)
    NATIVE_FORMATS: Set[Format] = set()
    IMPLIES_RECURSE: bool = False
    INTERNAL: bool = False
    PROGRAMS: Tuple[str, ...] = tuple()
    SUFFIX: str = "." + FORMAT_STR.lower()
    WORKING_SUFFIX: str = f"{PROGRAM_NAME}-tmp"

    def __init__(self, config: AttrDict, original_path: Path, format: Format):
        """Initialize handler."""
        self.config: AttrDict = config
        self.original_path: Path = original_path
        self.working_paths: Set[Path] = set()
        self.final_path: Path = self.original_path.with_suffix(self.SUFFIX)
        self.format: Format = format

    def get_working_path(self, identifier: str = "") -> Path:
        """Return a working path with a custom suffix."""
        suffixes = [self.original_path.suffix, self.WORKING_SUFFIX]
        if identifier:
            suffixes += [identifier]
        suffixes += [self.SUFFIX[1:]]

        suffix = ".".join(suffixes)
        return self.original_path.with_suffix(suffix)

    @staticmethod
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

    def _cleanup_after_optimize_aux(self, last_working_path: Path) -> Tuple[int, int]:
        """Replace old file with better one or discard new wasteful file."""
        bytes_in = 0
        bytes_out = 0
        try:
            bytes_in = self.original_path.stat().st_size
            bytes_out = last_working_path.stat().st_size
            if not self.config.test and (
                (bytes_out > 0) and ((bytes_out < bytes_in) or self.config.bigger)
            ):
                last_working_path.replace(self.final_path)
                if self.final_path != self.original_path:
                    self.working_paths.add(self.original_path)
                self.format = self.FORMAT
            else:
                self.working_paths.add(last_working_path)
                bytes_out = bytes_in
            if self.final_path in self.working_paths:
                self.working_paths.remove(self.final_path)
            for working_path in self.working_paths:
                working_path.unlink(missing_ok=True)
        except OSError as exc:
            print(exc)
            import traceback

            traceback.print_exc()

        return (bytes_in, bytes_out)

    def cleanup_after_optimize(self, last_working_path: Path) -> Tuple[int, int]:
        """
        Replace old file with better one or discard new wasteful file.

        And report results using the stats module.
        """
        return self._cleanup_after_optimize_aux(last_working_path)
