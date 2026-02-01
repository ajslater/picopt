"""FileType abstract class for image and container formats."""

import subprocess
import traceback
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from picopt.handlers.handler.cleanup import HandlerCleanup
from picopt.report import ReportStats

WORKING_PATH_TRANS_TABLE = str.maketrans(dict.fromkeys(" /", "_"))
INTERNAL: str = "internal"


class Handler(ABC, HandlerCleanup):
    """Handler base for image and container formats."""

    @classmethod
    def run_ext(cls, args: tuple[str, ...], input_buffer: BinaryIO) -> BytesIO:
        """Run EXTERNAL program."""
        for arg in args:
            # Guarantee tuple[str]
            if arg in (None, ""):
                reason = f"{args}"
                raise ValueError(reason)

        input_buffer.seek(0)
        proc = subprocess.run(  # noqa: S603
            args, check=True, input=input_buffer.read(), capture_output=True
        )
        return BytesIO(proc.stdout)

    def get_working_path(self) -> Path:
        """Return a working path with a custom suffix."""
        # Only used by webp handlers because they need disk file inputs
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

        suffixes = (
            *self.original_path.suffixes,
            self.WORKING_SUFFIX,
            "." + self.PROGRAMS[0][0],
            self.output_suffix,
        )
        suffix = "".join(suffixes)
        return path.with_suffix(suffix)

    def run_ext_fs(  # noqa: PLR0913
        self,
        args: tuple[str, ...],
        input_buffer: BinaryIO,
        input_path: Path | None,
        *,
        output_path: Path | None = None,  # unused by webp
        input_path_tmp: bool,
        output_path_tmp: bool = False,  # unused by webp
    ) -> BytesIO:
        """Run EXTERNAL program that lacks stdin/stdout streaming."""
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
            traceback.print_exc()
            report_stats = self.error(exc)
        if self.config.verbose:
            report_stats.report(self._printer)
        return report_stats
