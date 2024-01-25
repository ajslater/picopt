"""FileType abstract class for image and container formats."""
import shutil
import subprocess
from abc import ABC
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Optional

from confuse.templates import AttrDict
from termcolor import cprint

from picopt import PROGRAM_NAME
from picopt.data import PathInfo, ReportInfo
from picopt.stats import ReportStats


@dataclass(eq=True, frozen=True)
class FileFormat:
    """A file format, with image attributes."""

    format_str: str
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
    OUTPUT_FORMAT_STR: str = "unimplemented"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR, False, False)
    INTERNAL: str = "python_internal"
    PROGRAMS: MappingProxyType[str, Optional[str]] = MappingProxyType({})
    WORKING_SUFFIX: str = f"{PROGRAM_NAME}__tmp"

    @classmethod
    def init_programs(
        cls, programs: tuple[str, ...]
    ) -> MappingProxyType[str, Optional[str]]:
        """Initialize the PROGRAM map."""
        program_dict = {}
        for program in programs:
            if program.startswith("pil2") or program == cls.INTERNAL:
                bin_path = None
            else:
                bin_path = shutil.which(program)
                if not bin_path:
                    continue
            program_dict[program] = bin_path
        return MappingProxyType(program_dict)

    @staticmethod
    def run_ext(args: tuple[Optional[str], ...]) -> None:
        """Run EXTERNAL program."""
        for arg in args:
            # Guarantee tuple[str]
            if arg in (None, ""):
                reason = f"{args}"
                raise ValueError(reason)

        subprocess.run(
            args,  # noqa S603 # type: ignore
            check=True,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    @classmethod
    def native_input_file_formats(cls) -> frozenset[FileFormat]:
        """Return input formats handled without conversion."""
        return frozenset({cls.OUTPUT_FILE_FORMAT})

    @classmethod
    def is_handler_available(
        cls,
        convert_handlers: dict,
        available_programs: set,
        file_format: FileFormat,
    ):
        """Can this handler run with available programs."""
        handled_file_formats = cls.native_input_file_formats() | convert_handlers.get(
            cls, set()
        )
        return file_format in handled_file_formats and bool(
            available_programs & set(cls.PROGRAMS.keys())
        )

    @classmethod
    def get_default_suffix(cls):
        """Get the default suffix based on the format."""
        # overridden in jpeg
        return "." + cls.OUTPUT_FORMAT_STR.lower()

    @classmethod
    def get_suffixes(cls, default_suffix: str) -> frozenset:
        """Initialize suffix instance variables."""
        # overridden in jpeg
        return frozenset((default_suffix,))

    def __init__(
        self,
        config: AttrDict,
        path_info: PathInfo,
        input_file_format: FileFormat,
        metadata: Metadata,
    ):
        """Initialize handler."""
        self.config: AttrDict = config
        self.original_path: Path = path_info.path
        self.working_paths: set[Path] = set()
        default_suffix = self.get_default_suffix()
        self._suffixes = self.get_suffixes(default_suffix)
        self.output_suffix: str = (
            self.original_path.suffix
            if self.original_path
            and self.original_path.suffix.lower() in self._suffixes
            else default_suffix
        )
        self.final_path: Path = self.original_path.with_suffix(self.output_suffix)
        self.input_file_format: FileFormat = input_file_format
        self.metadata = metadata
        self.convert = input_file_format != self.OUTPUT_FILE_FORMAT
        self.is_case_sensitive = path_info.is_case_sensitive

    def get_working_path(self, identifier: str = "") -> Path:
        """Return a working path with a custom suffix."""
        suffixes = [self.original_path.suffix, self.WORKING_SUFFIX]
        if identifier:
            suffixes += [identifier]
        suffix = ".".join(suffixes)
        suffix += self.output_suffix
        return self.original_path.with_suffix(suffix)

    def cleanup_after_optimize(self, last_working_path: Path) -> tuple[int, int]:
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

                # Add original path to working_paths if the file has
                # a new name. But be careful of case sensitive fs.
                compare_final_str = str(self.final_path)
                compare_original_str = str(self.original_path)
                if not self.is_case_sensitive:
                    compare_final_str = compare_final_str.lower()
                    compare_original_str = compare_original_str.lower()
                if compare_final_str != compare_original_str:
                    self.working_paths.add(self.original_path)
            else:
                self.working_paths.add(last_working_path)
                bytes_out = bytes_in
            if self.final_path in self.working_paths:
                self.working_paths.remove(self.final_path)
            for working_path in self.working_paths:
                working_path.unlink(missing_ok=True)
        except OSError as exc:
            cprint(f"ERROR: cleanup_after_optimize: {exc}", "red")
            raise

        return (bytes_in, bytes_out)

    def error(self, exc: Exception) -> ReportStats:
        """Return an error result."""
        info = ReportInfo(self.original_path, self.convert, self.config.test, exc=exc)
        return ReportStats(info)
