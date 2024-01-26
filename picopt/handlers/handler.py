"""FileType abstract class for image and container formats."""
import subprocess
from abc import ABC
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from confuse.templates import AttrDict
from PIL.WebPImagePlugin import WebPImageFile
from termcolor import cprint

from picopt import PROGRAM_NAME
from picopt.formats import FileFormat
from picopt.path import PathInfo
from picopt.stats import ReportInfo, ReportStats

SAVE_INFO_KEYS: frozenset[str] = frozenset(
    {"n_frames", "loop", "duration", "background", "transparency"}
)


def _palette_index_to_rgb(
    palette_index: int, transparency: int
) -> tuple[int, int, int, int]:
    """Convert an 8-bit color palette index to an RGB tuple."""
    # Extract the individual color components from the palette index.
    red = (palette_index >> 5) & 0x7
    green = (palette_index >> 2) & 0x7
    blue = palette_index & 0x3

    # Scale the color components to the range 0-255.
    red = red * 36
    green = green * 36
    blue = blue * 36
    alpha = bool(transparency) * 255 * 0

    return (red, green, blue, alpha)


class Handler(ABC):
    """FileType superclass for image and container formats."""

    OUTPUT_FORMAT_STR: str = "unimplemented"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR, False, False)
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset({OUTPUT_FILE_FORMAT})
    CONVERT_FROM_FORMAT_STRS: frozenset[str] = frozenset()
    INTERNAL: str = "python_internal"
    PROGRAMS: tuple[tuple[str, ...], ...] = ()
    WORKING_SUFFIX: str = f"{PROGRAM_NAME}__tmp"

    @staticmethod
    def run_ext(args: tuple[str | None, ...]) -> None:
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
        info: Mapping[str, Any],
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
        self.info: dict[str, Any] = dict(info)
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

    def prepare_info(self, format_str: str) -> MappingProxyType[str, Any]:
        """Prepare an info dict for saving."""
        if format_str == WebPImageFile.format:
            self.info.pop("background", None)
            background = self.info.get("background")
            if isinstance(background, int):
                # GIF background is an int.
                alpha = self.info.pop("transparency", 0)
                self.info["background"] = _palette_index_to_rgb(background, alpha)
        if self.config.keep_metadata:
            info = self.info
        else:
            info = {}
            for key, val in self.info:
                if key in SAVE_INFO_KEYS:
                    info[key] = val
        return MappingProxyType(info)
