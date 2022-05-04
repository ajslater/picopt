"""Statistics for the optimization operations."""
from pathlib import Path
from typing import Optional

from humanize import naturalsize
from termcolor import cprint


class ReportStats:
    """Container for reported stats from optimization operations."""

    def __init__(
        self,
        path: Path,
        bytes_count: Optional[tuple[int, int]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Initialize required instance variables."""
        self.path = path
        self.error = error
        if bytes_count:
            self.bytes_in = bytes_count[0]
            self.bytes_out = bytes_count[1]
        else:
            self.bytes_in = 0
            self.bytes_out = 0

    def _new_percent_saved(self) -> str:
        """Spit out how much space the optimization saved."""
        size_in = self.bytes_in
        size_out = self.bytes_out
        if size_in <= 0:
            ratio = 1.0
        else:
            ratio = size_out / size_in
        saved = naturalsize(size_in - size_out)
        percent_saved = (1 - ratio) * 100

        result = "{:.{prec}f}% ({})".format(percent_saved, saved, prec=2)
        return result

    def _report_saved(self, test: bool) -> str:
        """Return the percent saved."""
        report = ""

        report += f"{self.path}: "
        report += self._new_percent_saved()
        if test:
            report += " could be saved."
        return report

    def report(self, test: bool, color="white") -> None:
        """Record the percent saved & print it."""
        if self.error:
            report = f"{self.path} error: {self.error}"
        else:
            report = self._report_saved(test)
        cprint(report, color)
