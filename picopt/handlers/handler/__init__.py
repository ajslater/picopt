"""FileType abstract class for image and container formats."""

import subprocess
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
            report_stats.report(self._printer)
        return report_stats
