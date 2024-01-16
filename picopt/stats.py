"""Statistics for the optimization operations."""
from dataclasses import dataclass, field
from subprocess import CalledProcessError
from typing import TYPE_CHECKING

from humanize import naturalsize
from termcolor import cprint

if TYPE_CHECKING:
    from termcolor._types import Attribute, Color

from picopt.data import ReportInfo


class ReportStats:
    """Container for reported stats from optimization operations."""

    _TAB = " " * 4

    def __init__(
        self,
        info: ReportInfo,
    ) -> None:
        """Initialize required instance variables."""
        self.path = info.path
        self.test = info.test
        self.convert = info.convert
        self.exc = info.exc
        self.bytes_in = info.bytes_in
        self.bytes_out = info.bytes_out
        self.saved = self.bytes_in - self.bytes_out

    def _new_percent_saved(self) -> str:
        """Spit out how much space the optimization saved."""
        ratio = 1.0 if self.bytes_in <= 0 else self.bytes_out / self.bytes_in
        saved = naturalsize(self.saved)
        percent_saved = (1 - ratio) * 100

        return f"{percent_saved:.2f}% ({saved})"

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
            report += f"\n{self._TAB}{self.exc!s}"
        return report

    def report(self) -> None:
        """Record the percent saved & print it."""
        attrs = []
        if self.exc:
            report = self._report_error()
            color: Color = "red"
        else:
            report = self._report_saved()
            color: Color = "cyan" if self.convert else "white"

            if self.saved <= 0:
                color: Color = "blue"
                attrs: list[Attribute] = ["bold"]

        cprint(report, color, attrs=attrs)


@dataclass
class Totals:
    """Totals for final report."""

    bytes_in: int = 0
    bytes_out: int = 0
    errors: list[ReportStats] = field(default_factory=list)
