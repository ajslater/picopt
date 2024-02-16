"""FileType abstract class for image and container formats."""
import os
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Mapping
from io import BufferedReader, BytesIO
from pathlib import Path
from types import MappingProxyType
from typing import Any, BinaryIO

from confuse.templates import AttrDict
from PIL.PngImagePlugin import PngImageFile, PngInfo
from PIL.WebPImagePlugin import WebPImageFile
from termcolor import cprint

from picopt import PROGRAM_NAME
from picopt.formats import PNGINFO_XMP_KEY, FileFormat
from picopt.path import CONTAINER_PATH_DELIMETER, PathInfo
from picopt.stats import ReportStats

SAVE_INFO_KEYS: frozenset[str] = frozenset(
    {"n_frames", "loop", "duration", "background"}
)
WORKING_PATH_TRANS_TABLE = str.maketrans({c: "_" for c in " /"})


def _gif_palette_index_to_rgb(
    palette_index: int,
) -> tuple[int, int, int]:
    """Convert an 8-bit color palette index to an RGB tuple."""
    # Extract the individual color components from the palette index.
    red = (palette_index >> 5) & 0x7
    green = (palette_index >> 2) & 0x7
    blue = palette_index & 0x3

    # Scale the color components to the range 0-255.
    red = red * 36
    green = green * 36
    blue = blue * 36

    return (red, green, blue)


class Handler(ABC):
    """FileType superclass for image and container formats."""

    OUTPUT_FORMAT_STR: str = "unimplemented"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(OUTPUT_FORMAT_STR, False, False)
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset({OUTPUT_FILE_FORMAT})
    CONVERT_FROM_FORMAT_STRS: frozenset[str] = frozenset()
    INTERNAL: str = "internal"
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
        result = subprocess.run(
            args,  # noqa: S603
            check=True,
            input=input_buffer.read(),
            stdout=subprocess.PIPE,
        )
        return BytesIO(result.stdout)

    def get_working_path(self, identifier: str) -> Path:
        """Return a working path with a custom suffix."""
        # Used by cwebp
        if cps := self.path_info.container_paths:
            path_tail = "__".join((*cps[1:], str(self.original_path)))
            path_tail = path_tail.translate(WORKING_PATH_TRANS_TABLE)
            path = Path(cps[0] + "__" + path_tail)
        else:
            path = self.original_path

        suffixes = [self.original_path.suffix, self.WORKING_SUFFIX]
        if identifier:
            suffixes += [identifier]
        suffix = ".".join(suffixes)
        suffix += self.output_suffix
        return path.with_suffix(suffix)

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
        self.path_info: PathInfo = path_info
        self.original_path: Path = (
            path_info.path if path_info.path else Path(path_info.name())
        )
        self.working_path = self.original_path
        default_suffix = self.get_default_suffix()
        self._suffixes = self.get_suffixes(default_suffix)
        suffix = path_info.suffix()
        self.output_suffix: str = (
            suffix if (suffix.lower() in self._suffixes) else default_suffix
        )
        self.final_path: Path = self.original_path.with_suffix(self.output_suffix)
        self.input_file_format: FileFormat = input_file_format
        self.info: dict[str, Any] = dict(info)
        if self.config.preserve:
            self.path_info.stat()
        self._input_file_formats = self.INPUT_FILE_FORMATS

    def prepare_info(self, format_str) -> MappingProxyType[str, Any]:
        """Prepare an info dict for saving."""
        if format_str == WebPImageFile.format:
            self.info.pop("background", None)
            background = self.info.get("background")
            if isinstance(background, int):
                # GIF background is an int.
                rgb = _gif_palette_index_to_rgb(background)
                self.info["background"] = (*rgb, 0)
        if format_str == PngImageFile.format:
            transparency = self.info.get("transparency")
            if isinstance(transparency, int):
                self.info.pop("transparency", None)
            if xmp := self.info.get("xmp", None):
                pnginfo = self.info.get("pnginfo", PngInfo())
                pnginfo.add_text(PNGINFO_XMP_KEY, xmp, zip=True)
                self.info["pnginfo"] = pnginfo
        if self.config.keep_metadata:
            info = self.info
        else:
            info = {}
            for key, val in self.info:
                if key in SAVE_INFO_KEYS:
                    info[key] = val
        return MappingProxyType(info)

    def run_ext_fs(  # noqa: PLR0913
        self,
        args: tuple[str | None, ...],
        input_buffer: BinaryIO,
        input_path: Path,
        output_path: Path,
        input_path_tmp: bool,
        output_path_tmp: bool,
    ) -> BinaryIO:
        """Run EXTERNAL program that lacks stdin/stdout streaming."""
        if input_path_tmp:
            with input_path.open("wb") as input_tmp_file, input_buffer:
                input_buffer.seek(0)
                input_tmp_file.write(input_buffer.read())

        subprocess.run(
            args,  # noqa S603 # type: ignore
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

        if isinstance(final_data_buffer, BytesIO):
            with self.final_path.open("wb") as final_file, final_data_buffer:
                final_data_buffer.seek(0)
                final_file.write(final_data_buffer.read())
        else:
            final_data_buffer.close()
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
        self, final_data_buffer: BinaryIO
    ) -> tuple[str, bytes]:
        """Save new data."""
        return_data = b""
        if (
            isinstance(final_data_buffer, BytesIO)
            or self.path_info.is_container_child()
        ):
            if self.path_info.is_container_child():
                # only return the data in the report for containers.
                final_data_buffer.seek(0)
                return_data = final_data_buffer.read()
            if isinstance(final_data_buffer, BufferedReader) and self.working_path:
                self.working_path.unlink(missing_ok=True)
        if self.path_info.path:
            self._cleanup_filesystem(final_data_buffer)
        cps = self.path_info.container_paths
        report_path = CONTAINER_PATH_DELIMETER.join((*cps, str(self.final_path)))
        return report_path, return_data

    def _cleanup_after_optimize(self, final_data_buffer: BinaryIO) -> ReportStats:
        """Replace old file with better one or discard new wasteful file."""
        try:
            bytes_in = self.path_info.bytes_in()
            bytes_out = self.get_buffer_len(final_data_buffer)
            if not self.config.test and (
                (bytes_out > 0) and ((bytes_out < bytes_in) or self.config.bigger)
            ):
                report_path, return_data = self._cleanup_after_optimize_save_new(
                    final_data_buffer
                )
            else:
                return_data = b""
                report_path = str(self.original_path)
            final_data_buffer.close()

        except Exception as exc:
            cprint(f"ERROR: cleanup_after_optimize: {exc}", "red")
            raise

        return ReportStats(
            report_path,
            path_info=self.path_info,
            config=self.config,
            bytes_in=bytes_in,
            bytes_out=bytes_out,
            data=return_data,
        )

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
            report_stats = self.error(exc)
        if self.config.verbose:
            report_stats.report()
        return report_stats
