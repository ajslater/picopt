"""Statistics for the optimization operations."""
from pathlib import Path
from typing import List, Optional, Tuple

from confuse.templates import AttrDict
from humanize import naturalsize


class ReportStats:
    """Container for reported stats from optimization operations."""

    def __init__(
        self,
        config: AttrDict,
        final_path: Path,
        report: Optional[str] = None,
        bytes_count: Optional[Tuple[int, int]] = None,
        errors: Optional[List[str]] = None,
    ) -> None:
        """Initialize required instance variables."""
        self.config = config
        self.final_path = final_path
        self.report_list = []
        self.errors = errors
        if report:
            self.report_list.append(report)
        if bytes_count:
            self.bytes_in = bytes_count[0]
            self.bytes_out = bytes_count[1]
        else:
            self.bytes_in = 0
            self.bytes_out = 0

    def new_percent_saved(self) -> str:
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

    def _report_saved(self) -> str:
        """Return the percent saved."""
        report = ""
        path = self.final_path

        report += f"{path}: "
        report += self.new_percent_saved()
        if self.config.test:
            report += " could be saved."
        if self.config.verbose > 1:
            tools_report = ", ".join(self.report_list)
            if tools_report:
                report += "\n\t" + tools_report
        return report

    def report_saved(self) -> None:
        """Record the percent saved & print it."""
        if self.config.verbose:
            report = self._report_saved()
            print(report)

    def report_totals(
        self,
    ) -> None:
        """Report the total number and percent of bytes saved."""
        if self.bytes_in:
            bytes_saved = self.bytes_in - self.bytes_out
            percent_bytes_saved = bytes_saved / self.bytes_in * 100
            msg = ""
            if self.config.test:
                if percent_bytes_saved > 0:
                    msg += "Could save"
                elif percent_bytes_saved == 0:
                    msg += "Could even out for"
                else:
                    msg += "Could lose"
            else:
                if percent_bytes_saved > 0:
                    msg += "Saved"
                elif percent_bytes_saved == 0:
                    msg += "Evened out"
                else:
                    msg = "Lost"
            msg += " a total of {} or {:.{prec}f}%".format(
                naturalsize(bytes_saved), percent_bytes_saved, prec=2
            )
            if self.config.verbose:
                print(msg)
                if self.config.test:
                    print("Test run did not change any files.")

        else:
            if self.config.verbose:
                print("Didn't optimize any files.")

        if self.errors:
            print("Errors with the following files:")
            for error in self.errors:
                print(f"{error[0]}: {error[1]}")
