"""
Handler base class.

This is the merger of the old three-class chain
``Handler -> HandlerCleanup -> HandlerInit``. There is no longer any reason
to split them; together they describe one concept (a unit of work that takes
a path-like input, optimizes it, and writes the result back).

Subclasses live in:

- :mod:`picopt.plugins.base.image` — :class:`ImageHandler`
- :mod:`picopt.plugins.base.container` — :class:`ContainerHandler`
- :mod:`picopt.plugins.base.archive` — :class:`ArchiveHandler`
- :mod:`picopt.plugins.base.animated` — :class:`ImageAnimated`
"""

from __future__ import annotations

import os
import subprocess
import traceback
from abc import ABC, abstractmethod
from io import BufferedReader, BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

from picopt import WORKING_SUFFIX
from picopt.path import DOUBLE_SUFFIX, PathInfo
from picopt.plugins.base.format import FileFormat
from picopt.printer import Printer
from picopt.report import ReportStats

if TYPE_CHECKING:
    from confuse.templates import AttrDict

    from picopt.plugins.base.tool import Tool

# Used by working-path construction for nested-container scratch files.
_WORKING_PATH_TRANS_TABLE: dict[int, str] = str.maketrans(dict.fromkeys(" /", "_"))


class Handler(ABC):
    """
    Base class for every picopt handler.

    Class attributes that subclasses override:

    - ``OUTPUT_FORMAT_STR``: uppercase format key, e.g. ``"PNG"``.
    - ``OUTPUT_FILE_FORMAT``: the canonical FileFormat this handler emits.
    - ``INPUT_FILE_FORMATS``: which FileFormats can be fed to this handler
      without an intermediate PIL conversion.
    - ``SUFFIXES``: file extensions this handler claims (first is canonical).
    - ``PIPELINE``: tuple-of-tuples of :class:`Tool` instances. The outer
      tuple is sequential pipeline tiers; each inner tuple is alternatives
      for that tier. This replaces the old ``PROGRAMS`` mechanism.
    """

    SUFFIXES: tuple[str, ...] = ()
    OUTPUT_FORMAT_STR: str = "UNIMPLEMENTED"
    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(
        "UNIMPLEMENTED", lossless=False, animated=False
    )
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset()
    PIPELINE: tuple[tuple[Tool, ...], ...] = ()

    # ------------------------------------------------------------------ init

    def __init__(
        self,
        config: AttrDict,
        path_info: PathInfo,
        input_file_format: FileFormat,
    ) -> None:
        """Initialize handler state."""
        self.config: AttrDict = config
        self.path_info: PathInfo = path_info
        self._printer: Printer = Printer(self.config.verbose)

        # Paths
        self.original_path: Path = path_info.path or Path(path_info.name())
        self.working_path: Path = self.original_path

        # Suffixes
        default_suffix = (
            self.SUFFIXES[0] if self.SUFFIXES else "." + self.OUTPUT_FORMAT_STR.lower()
        )
        suffix = path_info.suffix()
        self.output_suffix: str = (
            suffix if suffix.lower() in self.SUFFIXES else default_suffix
        )
        self.final_path: Path = self._compute_final_path()

        if self.config.preserve:
            self.path_info.stat()

        # For container repack and older cwebp which only accepts some formats
        self.input_file_format: FileFormat = input_file_format
        self._input_file_formats: frozenset[FileFormat] = self.INPUT_FILE_FORMATS
        self._original_mtime = self.path_info.mtime()

    def _compute_final_path(self) -> Path:
        """Compute the final path even if the original has multiple suffixes."""
        final_path = self.original_path.with_suffix("")
        if final_path.suffix == DOUBLE_SUFFIX:
            final_path = final_path.with_suffix("")
        return final_path.parent / (final_path.name + self.output_suffix)

    # ----------------------------------------------------------- subprocess

    @classmethod
    def run_ext(cls, args: tuple[str, ...], input_buffer: BinaryIO) -> BytesIO:
        """Run an external program over a stdin/stdout buffer."""
        for arg in args:
            if arg in (None, ""):
                msg = f"Empty argv element in: {args}"
                raise ValueError(msg)
        input_buffer.seek(0)
        proc = subprocess.run(  # noqa: S603
            args,
            check=True,
            input=input_buffer.read(),
            capture_output=True,
        )
        return BytesIO(proc.stdout)

    def run_ext_fs(
        self,
        args: tuple[str, ...],
        input_buffer: BinaryIO,
        input_path: Path | None,
        *,
        output_path: Path | None = None,
        input_path_tmp: bool,
        output_path_tmp: bool = False,
    ) -> BytesIO:
        """Run an external program that needs real filesystem paths."""
        if input_path_tmp and input_path:
            with input_path.open("wb") as input_tmp_file, input_buffer:
                input_buffer.seek(0)
                input_tmp_file.write(input_buffer.read())

        proc = subprocess.run(  # noqa: S603
            args,
            check=True,
            capture_output=True,
        )

        if input_path_tmp and input_path:
            input_path.unlink(missing_ok=True)

        if output_path_tmp and output_path:
            output_buffer = BytesIO(output_path.read_bytes())
            output_path.unlink(missing_ok=True)
        else:
            output_buffer = BytesIO(proc.stdout)
        return output_buffer

    def get_working_path(self) -> Path:
        """Working path with a custom suffix; used for tools that need real files."""
        if container_parents := self.path_info.container_parents:
            path_head = container_parents[0]
            path_tail = "__".join((*container_parents[1:], str(self.original_path)))
            path_tail = path_tail.translate(_WORKING_PATH_TRANS_TABLE)
            path = type(self.original_path)(f"{path_head}__{path_tail}")
        else:
            path = self.original_path

        first_tool_name = next(
            (tool.name for tier in self.PIPELINE for tool in tier if tool.name),
            "",
        )

        suffixes = (
            *self.original_path.suffixes,
            WORKING_SUFFIX,
            f".{first_tool_name}" if first_tool_name else "",
            self.output_suffix,
        )
        return path.with_suffix("".join(s for s in suffixes if s))

    # ---------------------------------------------------------- run pipeline

    def selected_stages(self) -> tuple[Tool, ...]:
        """
        Return the per-tier Tools the config layer probed and selected.

        Populated by ``config/handlers.py`` during setup. Empty tuple means
        the handler has no pipeline (e.g. archives that pack via internal
        Python libraries).
        """
        return self.config.computed.handler_stages.get(type(self), ())

    def first_stage(self) -> Tool:
        """Return the first selected stage; raise if pipeline is empty."""
        stages = self.selected_stages()
        if not stages:
            msg = f"{type(self).__name__} has no available pipeline stages"
            raise ValueError(msg)
        return stages[0]

    @classmethod
    def resolved_tool(cls, tool_class: type[Tool]) -> Tool:
        """
        Return the class-level (already-probed) instance of ``tool_class``.

        The PIPELINE attribute holds singleton Tool instances; the config
        layer's startup probe populates each instance's cached binary path.
        Container handlers whose ``walk()`` needs to invoke the same external
        tool that's also their packing tool (WebPMux is the canonical case)
        use this to reach the resolved instance without hard-coding the
        binary name.
        """
        for tier in cls.PIPELINE:
            for tool in tier:
                if isinstance(tool, tool_class):
                    return tool
        msg = f"{tool_class.__name__} not found in {cls.__name__}.PIPELINE"
        raise LookupError(msg)

    @abstractmethod
    def optimize(self) -> BinaryIO:
        """Implement how to run their pipeline in the subclass."""

    def error(self, exc: Exception) -> ReportStats:
        """Return an error result."""
        return ReportStats(self.original_path, exc=exc)

    def optimize_wrapper(self) -> ReportStats:
        """Run optimize() and convert the result into a ReportStats record."""
        try:
            buffer = self.optimize()
            report_stats = self._cleanup_after_optimize(buffer)
        except Exception as exc:
            traceback.print_exc()
            report_stats = self.error(exc)
        if self.config.verbose:
            report_stats.report(self._printer)
        return report_stats

    # --------------------------------------------------------------- cleanup

    def _get_buffer_len(self, buffer: BinaryIO) -> int:
        if isinstance(buffer, BufferedReader):
            return self.working_path.stat().st_size
        if isinstance(buffer, BytesIO):
            return buffer.getbuffer().nbytes
        msg = f"Unknown type for input_buffer: {type(buffer)}"
        raise TypeError(msg)

    def _save_new_data(self, final_data_buffer: BinaryIO | None) -> bytes:
        if final_data_buffer is None:
            return b""
        if isinstance(final_data_buffer, BytesIO) or bool(self.path_info.archiveinfo):
            final_data_buffer.seek(0)
            return final_data_buffer.read()
        return b""

    def _write_final_path(self, final_data_buffer: BinaryIO) -> None:
        if isinstance(final_data_buffer, BytesIO):
            with self.working_path.open("wb") as working_path:
                final_data_buffer.seek(0)
                working_path.write(final_data_buffer.read())
        self.working_path.replace(self.final_path)

    def _cleanup_original_path(self) -> None:
        final_norm = os.path.normcase(self.final_path)
        original_norm = os.path.normcase(self.original_path)
        if not self.path_info.is_case_sensitive:
            final_norm = final_norm.lower()
            original_norm = original_norm.lower()
        if final_norm != original_norm:
            self.original_path.unlink(missing_ok=True)

    def _preserve_stats(self) -> None:
        if not self.config.preserve:
            return
        stat = self.path_info.stat()
        if stat is None:
            return
        os.chown(self.final_path, stat.st_uid, stat.st_gid)
        self.final_path.chmod(stat.st_mode)
        os.utime(self.final_path, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    def _cleanup_filesystem(self, final_data_buffer: BinaryIO) -> None:
        if not self.final_path:
            msg = "no buffer and no final path."
            raise ValueError(msg)
        self._write_final_path(final_data_buffer)
        final_data_buffer.close()
        self._cleanup_original_path()
        self._preserve_stats()

    def _cleanup_after_optimize_get_return_data(
        self, final_data_buffer: BinaryIO, bytes_in: int, bytes_out: int
    ) -> bytes:
        if not self.config.dry_run and (
            bytes_out > 0 and (bytes_out < bytes_in or self.config.bigger)
        ):
            return_data = self._save_new_data(final_data_buffer)
            if self.path_info.path:
                self._cleanup_filesystem(final_data_buffer)
        else:
            return_data = b""
        final_data_buffer.close()
        return return_data

    def _cleanup_after_optimize(self, final_data_buffer: BinaryIO) -> ReportStats:
        """Replace the old file with the better one or discard the new wasteful one."""
        bytes_in = self.path_info.bytes_in()
        bytes_out = self._get_buffer_len(final_data_buffer)
        return_data = self._cleanup_after_optimize_get_return_data(
            final_data_buffer, bytes_in, bytes_out
        )
        if (
            self.working_path
            and self.working_path != self.final_path
            and isinstance(final_data_buffer, BufferedReader)
        ):
            self.working_path.unlink(missing_ok=True)
        converted = self.original_path != self.final_path
        if converted:
            self.path_info.rename(self.final_path)
        # For in-archive entries final_path is a synthetic name with no
        # filesystem reality; whether the entry "changed" is decided by
        # whether the worker produced replacement bytes. The parent
        # container's repack pass owns the real timestamp.
        if self.path_info.path is None:
            changed = bool(return_data)
        else:
            changed = self.final_path.stat().st_mtime != self._original_mtime
        return ReportStats(
            self.final_path,
            converted=converted,
            path_info=self.path_info,
            config=self.config,
            bytes_in=bytes_in,
            bytes_out=bytes_out,
            data=return_data,
            changed=changed,
        )

    # ---------------------------------------------------------- detection

    @classmethod
    def identify_format(cls, path_info: PathInfo) -> FileFormat | None:
        """
        Default suffix-based identification.

        Most plugins instead provide a :class:`~picopt.plugins.base.plugin.Detector`
        subclass on their PLUGIN descriptor; that takes precedence. This
        method exists for handlers that want a trivial fallback (e.g. SVG).
        """
        suffix = path_info.suffix().lower()
        if suffix and suffix in cls.SUFFIXES:
            return cls.OUTPUT_FILE_FORMAT
        return None
