"""Statistics for the optimization operations."""
from dataclasses import dataclass, field
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

    def _report_saved(self, test: bool) -> str:
        """Return the percent saved."""
        report = ""

        report += f"{self.path}: "
        report += self._new_percent_saved()
        if test:
            report += " could be saved."
        return report

    def report(self, test: bool, convert=False) -> None:
        """Record the percent saved & print it."""
        attrs = []
        if self.error:
            report = f"{self.path} error: {self.error}"
            color = "red"
        else:
            report = self._report_saved(test)
            if convert:
                color = "cyan"
            else:
                color = "white"

            if self.saved <= 0:
                attrs = ["dark", "bold"]

        cprint(report, color, attrs=attrs)


@dataclass
class Totals:
    """Totals for final report."""

    bytes_in: int = 0
    bytes_out: int = 0
    errors: list[ReportStats] = field(default_factory=list)
