"""Per-file optimization result record."""

from __future__ import annotations

from subprocess import CalledProcessError
from typing import TYPE_CHECKING

from humanize import naturalsize

if TYPE_CHECKING:
    from pathlib import Path

    from picopt.config.settings import PicoptSettings
    from picopt.path import PathInfo


class ReportStats:
    """Container for reported stats from optimization operations."""

    _TAB: str = " " * 4

    def __init__(  # noqa: PLR0913
        self,
        path: Path,
        *,
        bytes_in: int = 0,
        bytes_out: int = 0,
        exc: BaseException | None = None,
        data: bytes = b"",
        config: PicoptSettings | None = None,
        path_info: PathInfo | None = None,
        converted: bool = False,
        changed: bool = False,
    ) -> None:
        """Initialize required instance variables."""
        self.path: Path | None = path
        self.bytes_in: int = bytes_in
        self.bytes_out: int = bytes_out
        self.exc: BaseException | None = exc
        self.data: bytes = data
        self.changed: bool = changed
        # Don't store these large data structs, just tidbits.
        self.bigger: bool = config.bigger if config else False
        self.test: bool = config.dry_run if config else False
        self.convert: bool = path_info.convert if path_info else False
        self._full_name: str = path_info.full_output_name() if path_info else str(path)
        self.saved: int = self.bytes_in - self.bytes_out
        self.converted: bool = converted

    def _new_percent_saved(self) -> str:
        """Spit out how much space the optimization saved."""
        ratio = 1.0 if self.bytes_in <= 0 else self.bytes_out / self.bytes_in
        saved = naturalsize(self.saved)
        percent_saved = (1 - ratio) * 100

        return f"{percent_saved:.2f}% ({saved})"

    def _report_saved(self) -> str:
        """Return the percent saved."""
        report = f"{self._full_name}: "
        report += self._new_percent_saved()
        if self.test:
            report += " would be"
        if self.saved > 0:
            report += " saved"
        elif self.saved < 0:
            report += " lost"
        if self.saved <= 0 and not self.bigger:
            report += ", kept original"

        return report

    def _report_error(self) -> str:
        """Return the error report string."""
        report = f"{self._full_name}\n"
        if isinstance(self.exc, CalledProcessError):
            report += f"\n{self._TAB}retcode: {self.exc.returncode}"
            if self.exc.cmd:
                cmd = " ".join(self.exc.cmd)
                report += f"\n{self._TAB}command: {cmd}"
            if self.exc.stdout:
                report += f"\n{self._TAB}stdout: {self.exc.stdout}"
            if self.exc.stderr:
                report += f"\n{self._TAB}stderr: {self.exc.stderr}"
        else:
            report += f"\n{self._TAB}{self.exc!s}"
        return report

    def report_text(self) -> str:
        """Return the human-readable line for this report."""
        return self._report_error() if self.exc else self._report_saved()
