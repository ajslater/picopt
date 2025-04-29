"""Handler Init."""

from pathlib import Path

from confuse.templates import AttrDict

from picopt import PROGRAM_NAME
from picopt.formats import FileFormat
from picopt.path import PathInfo
from picopt.printer import Printer

_BAD_SUFFIX_CHARS = " ()"
_MAX_SUFFIX_LEN = 8


class HandlerInit:
    """Handler init."""

    # if multiple suffixes, default suffix is first. Otherwise generated from OUTPUT_FORMAT_STR.
    SUFFIXES = ()
    OUTPUT_FORMAT_STR: str = "unimplemented"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(
        OUTPUT_FORMAT_STR, lossless=False, animated=False
    )
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS: tuple[tuple[str, ...], ...] = ()
    WORKING_SUFFIX: str = f"{PROGRAM_NAME}-tmp"

    def _compute_final_path(self):
        """Compute the final path even if it the original has multiple suffixes."""
        final_path = str(self.original_path)
        for suffix in reversed(self.original_path.suffixes):
            if len(suffix) > _MAX_SUFFIX_LEN or any(
                char in suffix for char in _BAD_SUFFIX_CHARS
            ):
                # dots in filenames are different than multiple suffixes
                # bail if it doesn't look like a suffix
                break
            final_path = final_path.removesuffix(suffix)
        final_path += self.output_suffix
        return Path(final_path)

    def __init__(
        self,
        config: AttrDict,
        path_info: PathInfo,
        input_file_format: FileFormat,
    ):
        """Initialize handler."""
        self.config: AttrDict = config
        self.path_info: PathInfo = path_info
        self._printer = Printer(self.config.verbose)

        # Paths
        self.original_path: Path = (
            path_info.path if path_info.path else Path(path_info.name())
        )
        self.working_path = self.original_path

        # Suffixes
        default_suffix = (
            self.SUFFIXES[0] if self.SUFFIXES else "." + self.OUTPUT_FORMAT_STR.lower()
        )
        suffix = path_info.suffix()
        self.output_suffix: str = (
            suffix if (suffix.lower() in self.SUFFIXES) else default_suffix
        )
        self.final_path: Path = self._compute_final_path()

        if self.config.preserve:
            self.path_info.stat()

        # For container repack and older cwebp which only accepts some formats
        self.input_file_format = input_file_format
        self._input_file_formats = self.INPUT_FILE_FORMATS
