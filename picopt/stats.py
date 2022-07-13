"""Statistics for the optimization operations."""
from dataclasses import dataclass, field
from pathlib import Path
from subprocess import CalledProcessError
from typing import Optional

from humanize import naturalsize
from termcolor import cprint


class ReportStats:
    """Container for reported stats from optimization operations."""

    _TAB = " " * 4

    def __init__(
        self,
        path: Path,
        bytes_count: Optional[tuple[int, int]],
        test: bool,
        convert: bool,
        exc: Optional[Exception] = None,
    ) -> None:
        """Initialize required instance variables."""
        self.path = path
        self.test = test
        self.convert = convert
        self.exc = exc
        if bytes_count:
            self.bytes_in = bytes_count[0]
            self.bytes_out = bytes_count[1]
        else:
            self.bytes_in = 0
            self.bytes_out = 0
        self.saved = self.bytes_in - self.bytes_out

    def _new_percent_saved(self) -> str:
        """Spit out how much space the optimization saved."""
        if self.bytes_in <= 0:
            ratio = 1.0
        else:
            ratio = self.bytes_out / self.bytes_in
        saved = naturalsize(self.saved)
        percent_saved = (1 - ratio) * 100

        result = "{:.{prec}f}% ({})".format(percent_saved, saved, prec=2)
        return result

    def _report_saved(self) -> str:
        """Return the percent saved."""
        report = ""

        report += f"{self.path}: "
        report += self._new_percent_saved()
        if self.test:
            report += " could be saved."
        return report

    def _report_error(self) -> str:
        """Return the error report string."""
        report = f"ERROR: {self.path}"
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
            report += f"\n{self._TAB}{str(self.exc)}"
        return report

    def report(self) -> None:
        """Record the percent saved & print it."""
        attrs = []
        if self.exc:
            report = self._report_error()
            color = "red"
        else:
            report = self._report_saved()
            if self.convert:
                color = "cyan"
            else:
                color = "white"

            if self.saved <= 0:
                color = "blue"
                attrs = ["bold"]

        cprint(report, color, attrs=attrs)


@dataclass
class Totals:
    """Totals for final report."""

    bytes_in: int = 0
    bytes_out: int = 0
    errors: list[ReportStats] = field(default_factory=list)
