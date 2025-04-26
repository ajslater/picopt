"""FileType abstract class for image and container formats."""

import os
import subprocess
from abc import ABC, abstractmethod
from io import BufferedReader, BytesIO
from pathlib import Path
from typing import BinaryIO

from confuse.templates import AttrDict
from termcolor import cprint

from picopt import PROGRAM_NAME
from picopt.formats import FileFormat
from picopt.path import PathInfo
from picopt.stats import ReportStats

WORKING_PATH_TRANS_TABLE = str.maketrans(dict.fromkeys(" /", "_"))
INTERNAL: str = "internal"


class Handler(ABC):
    """FileType superclass for image and container formats."""

    OUTPUT_FORMAT_STR: str = "unimplemented"
    # if multiple suffixes, default suffix is first. Otherwise generated from OUTPUT_FORMAT_STR.
    SUFFIXES = ()
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(
        OUTPUT_FORMAT_STR, lossless=False, animated=False
    )
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS: tuple[tuple[str, ...], ...] = ()
    WORKING_SUFFIX: str = f"{PROGRAM_NAME}-tmp"

    @classmethod
    def run_ext(cls, args: tuple[str, ...], input_buffer: BinaryIO) -> BytesIO:
        """Run EXTERNAL program."""
        for arg in args:
            # Guarantee tuple[str]
            if arg in (None, ""):
                reason = f"{args}"
                raise ValueError(reason)

        input_buffer.seek(0)
        result = subprocess.run(  # noqa: S603
            args,
            check=True,
            input=input_buffer.read(),
            stdout=subprocess.PIPE,
        )
        return BytesIO(result.stdout)

    def get_working_path(self, identifier_suffix: str) -> Path:
        """Return a working path with a custom suffix."""
        # Only used by cwebp because it needs to use disk
        if container_parents := self.path_info.container_parents:
            # The first entry is a real file on disk.
            path_head = container_parents[0]
            # The rest are containers inside containers.
            path_tail = "__".join((*container_parents[1:], str(self.original_path)))
            path_tail = path_tail.translate(WORKING_PATH_TRANS_TABLE)
            path_str = f"{path_head}__{path_tail}"
            path = Path(path_str)
        else:
            path = self.original_path

        suffixes = [self.original_path.suffix, self.WORKING_SUFFIX]
        if identifier_suffix:
            suffixes += [identifier_suffix]
        suffix = ".".join(suffixes)
        suffix += self.output_suffix
        return path.with_suffix(suffix)

    def __init__(
        self,
        config: AttrDict,
        path_info: PathInfo,
        input_file_format: FileFormat,
    ):
        """Initialize handler."""
        self.config: AttrDict = config
        self.path_info: PathInfo = path_info

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

        # Handle replacing multiple suffixes
        final_path = str(self.original_path)
        for suffix in reversed(self.original_path.suffixes):
            final_path = final_path.removesuffix(suffix)
        final_path = Path(final_path)
        final_path = final_path.with_suffix(self.output_suffix)
        self.final_path: Path = final_path

        if self.config.preserve:
            self.path_info.stat()

        # For container repack and older cwebp which only accepts some formats
        self.input_file_format = input_file_format
        self._input_file_formats = self.INPUT_FILE_FORMATS

        # For writing archives in place on the disk
        self._bytes_in = 0
        self._optimize_in_place_on_disk = False

    def run_ext_fs(  # noqa: PLR0913
        self,
        args: tuple[str | None, ...],
        input_buffer: BinaryIO,
        input_path: Path,
        output_path: Path,
        *,
        input_path_tmp: bool,
        output_path_tmp: bool,
    ) -> BinaryIO:
        """Run EXTERNAL program that lacks stdin/stdout streaming."""
        if input_path_tmp:
            with input_path.open("wb") as input_tmp_file, input_buffer:
                input_buffer.seek(0)
                input_tmp_file.write(input_buffer.read())

        subprocess.run(  # noqa: S603
            args,  # type: ignore[reportArgumentType]
            check=True,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        if input_path_tmp:
            input_path.unlink(missing_ok=True)

        if output_path_tmp:
            with output_path.open("rb") as output_tmp_file:
                output_buffer = BytesIO(output_tmp_file.read())
            output_path.unlink(missing_ok=True)
        else:
            self.working_path = output_path
            output_buffer = output_path.open("rb")
        return output_buffer

    def _cleanup_filesystem(self, final_data_buffer: BinaryIO) -> None:
        """Write file to filesystem and clean up."""
        if not self.final_path:
            reason = "This should not happen. no buffer and no final path."
            raise ValueError(reason)

        with final_data_buffer:
            if not self._optimize_in_place_on_disk:
                if isinstance(final_data_buffer, BytesIO):
                    with self.final_path.open("wb") as final_file:
                        final_data_buffer.seek(0)
                        final_file.write(final_data_buffer.read())
                else:
                    self.working_path.replace(self.final_path)

        ###########
        # CLEANUP #
        ###########
        # Remove original path if the file has
        # a new name. But be careful of case sensitive fs.
        compare_final_str = str(self.final_path)
        compare_original_str = str(self.original_path)
        if not self.path_info.is_case_sensitive:
            compare_final_str = compare_final_str.lower()
            compare_original_str = compare_original_str.lower()
        if compare_final_str != compare_original_str:
            self.original_path.unlink(missing_ok=True)

        ###############################
        # RESTORE STATS TO FINAL PATH #
        ###############################
        if self.config.preserve:
            stat = self.path_info.stat()
            if stat and stat is not True:
                os.chown(self.final_path, stat.st_uid, stat.st_gid)
                self.final_path.chmod(stat.st_mode)
                os.utime(
                    self.final_path,
                    ns=(stat.st_atime_ns, stat.st_mtime_ns),
                )

    def get_buffer_len(self, buffer: BinaryIO) -> int:
        """Return buffer size."""
        if isinstance(buffer, BufferedReader):
            size = self.working_path.stat().st_size
        elif isinstance(buffer, BytesIO):
            size = buffer.getbuffer().nbytes
        else:
            reason = f"Unknown type for input_buffer: {type(buffer)}"
            raise TypeError(reason)
        return size

    def _cleanup_after_optimize_save_new(
        self, final_data_buffer: BinaryIO | None
    ) -> bytes:
        """Save new data."""
        return_data = b""
        if final_data_buffer is None:
            return return_data
        if isinstance(final_data_buffer, BytesIO) or bool(self.path_info.archiveinfo):
            # only return the data in the report for containers.
            final_data_buffer.seek(0)
            return_data = final_data_buffer.read()
        if self.path_info.path:
            self._cleanup_filesystem(final_data_buffer)
        return return_data

    def _cleanup_after_optimize(self, final_data_buffer: BinaryIO) -> ReportStats:
        """Replace old file with better one or discard new wasteful file."""
        try:
            if self._optimize_in_place_on_disk:
                bytes_in = self._bytes_in
                bytes_out = self.final_path.stat().st_size
            else:
                bytes_in = self.path_info.bytes_in()
                bytes_out = self.get_buffer_len(final_data_buffer)
            if not self.config.dry_run and (
                (bytes_out > 0) and ((bytes_out < bytes_in) or self.config.bigger)
            ):
                return_data = self._cleanup_after_optimize_save_new(final_data_buffer)
            else:
                return_data = b""
            final_data_buffer.close()
            if (
                self.working_path
                and self.working_path != self.final_path
                and isinstance(final_data_buffer, BufferedReader)
            ):
                self.working_path.unlink(missing_ok=True)
            return ReportStats(
                self.final_path,
                path_info=self.path_info,
                config=self.config,
                bytes_in=bytes_in,
                bytes_out=bytes_out,
                data=return_data,
            )
        except Exception as exc:
            cprint(f"ERROR: cleanup_after_optimize: {self.final_path} {exc}", "red")
            raise

    @abstractmethod
    def optimize(self) -> BinaryIO:
        """Implement by subclasses."""

    def error(self, exc: Exception) -> ReportStats:
        """Return an error result."""
        return ReportStats(self.original_path, exc=exc)

    def optimize_wrapper(self) -> ReportStats:
        """Wrap subclass optimize."""
        try:
            buffer = self.optimize()
            report_stats = self._cleanup_after_optimize(buffer)
        except Exception as exc:
            import traceback

            traceback.print_exc()
            report_stats = self.error(exc)
        if self.config.verbose:
            report_stats.report()
        return report_stats
