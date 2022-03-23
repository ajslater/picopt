"""FileType abstract class for image and container formats."""
import subprocess

from abc import ABC
from dataclasses import dataclass
from pathlib import Path

from confuse.templates import AttrDict

from picopt import PROGRAM_NAME
from picopt.stats import ReportStats


@dataclass(eq=True, frozen=True)
class Format:
    """A file format, with image attributes."""

    format: str
    lossless: bool = True
    animated: bool = False


@dataclass(eq=True, frozen=True)
class Metadata:
    """Image metadata class."""

    exif: bytes = b""
    icc_profile: str = ""
    n_frames: int = 1


class Handler(ABC):
    """FileType superclass for image and container formats."""

    BEST_ONLY: bool = True
    OUTPUT_FORMAT: str = "unimplemented"
    OUTPUT_FORMAT_OBJ: Format = Format(OUTPUT_FORMAT, False, False)
    INTERNAL: str = "python_internal"
    PROGRAMS: tuple[str, ...] = tuple()
    WORKING_SUFFIX: str = f"{PROGRAM_NAME}-tmp"

    @staticmethod
    def run_ext(args: tuple[str, ...]) -> None:
        """Run EXTERNAL program."""
        try:
            subprocess.check_call(args)
        except subprocess.CalledProcessError as exc:
            print(exc)
            print(exc.cmd)
            print(exc.returncode)
            print(exc.output)
            raise

    @classmethod
    def native_input_format_objs(cls) -> set[Format]:
        """Return input formats handled without conversion."""
        return set([cls.OUTPUT_FORMAT_OBJ])

    @classmethod
    def _output_suffix(cls) -> str:
        """Return the suffix without a leading dot."""
        return cls.OUTPUT_FORMAT.lower()

    @classmethod
    def output_suffix(cls) -> str:
        """Generate the output suffix for the handler."""
        return "." + cls._output_suffix()

    @classmethod
    def is_handler_available(
        cls,
        convert_handlers: dict,
        available_programs: set,
        format_obj: Format,
    ):
        """Can this handler run with available programs."""
        handled_format_objs = cls.native_input_format_objs() | convert_handlers.get(
            cls, set()
        )
        return format_obj in handled_format_objs and bool(
            available_programs & set(cls.PROGRAMS)
        )

    def __init__(
        self,
        config: AttrDict,
        original_path: Path,
        input_format_obj: Format,
        metadata: Metadata,
    ):
        """Initialize handler."""
        self.config: AttrDict = config
        self.original_path: Path = original_path
        self.working_paths: set[Path] = set()
        self.final_path: Path = self.original_path.with_suffix(self.output_suffix())
        self.input_format_obj: Format = input_format_obj
        self.metadata = metadata

    def get_working_path(self, identifier: str = "") -> Path:
        """Return a working path with a custom suffix."""
        suffixes = [self.original_path.suffix, self.WORKING_SUFFIX]
        if identifier:
            suffixes += [identifier]
        suffixes += [self._output_suffix()]
        suffix = ".".join(suffixes)

        return self.original_path.with_suffix(suffix)

    def _cleanup_after_optimize_aux(self, last_working_path: Path) -> tuple[int, int]:
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
            else:
                self.working_paths.add(last_working_path)
                bytes_out = bytes_in
            if self.final_path in self.working_paths:
                self.working_paths.remove(self.final_path)
            for working_path in self.working_paths:
                working_path.unlink(missing_ok=True)
        except OSError as exc:
            print(exc)

        return (bytes_in, bytes_out)

    def cleanup_after_optimize(self, last_working_path: Path) -> tuple[int, int]:
        """
        Replace old file with better one or discard new wasteful file.

        And report results using the stats module.
        """
        return self._cleanup_after_optimize_aux(last_working_path)

    def error(self, exc: Exception) -> ReportStats:
        """Return an error result."""
        report_stats = ReportStats(self.original_path, error=str(exc))
        if self.config.verbose:
            report_stats.report(self.config.test)
        return report_stats
