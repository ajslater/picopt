"""Statistics for the optimization operations."""
from dataclasses import dataclass
from pathlib import Path
from subprocess import CalledProcessError
from typing import TYPE_CHECKING

from confuse import AttrDict
from humanize import naturalsize
from termcolor import cprint

from picopt.path import PathInfo

if TYPE_CHECKING:
    from termcolor._types import Attribute, Color


@dataclass
class ReportStatBase:
    """Base dataclass for ReportStats."""

    path: Path | None
    bytes_in: int = 0
    bytes_out: int = 0
    exc: Exception | None = None
    data: bytes = b""


class ReportStats(ReportStatBase):
    """Container for reported stats from optimization operations."""

    _TAB = " " * 4

    def __init__(
        self,
        *args,
        config: AttrDict | None = None,
        path_info: PathInfo | None = None,
        **kwargs,
    ) -> None:
        """Initialize required instance variables."""
        # Don't store these large data structs, just tidbits.
        self.bigger: bool = config.bigger if config else False
        self.test: bool = config.test if config else False
        self.convert: bool = path_info.convert if path_info else False
        self.in_container: bool = path_info.is_container_child() if path_info else False
        super().__init__(*args, **kwargs)
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
        if self.in_container:
            report += "  "
        report += f"{self.path}: "
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


class Totals:
    """Totals for final report."""

    def __init__(self, config: AttrDict):
        """Initialize Totals."""
        self.bytes_in: int = 0
        self.bytes_out: int = 0
        self.errors: list[ReportStats] = []
        self._config: AttrDict = config

    ##########
    # Finish #
    ##########
    def _report_bytes_in(self) -> None:
        """Report Totals if there were bytes in."""
        if not self._config.verbose and not self._config.test:
            return
        bytes_saved = self.bytes_in - self.bytes_out
        percent_bytes_saved = bytes_saved / self.bytes_in * 100
        msg = ""
        if self._config.test:
            if percent_bytes_saved > 0:
                msg += "Could save"
            elif percent_bytes_saved == 0:
                msg += "Could even out for"
            else:
                msg += "Could lose"
        elif percent_bytes_saved > 0:
            msg += "Saved"
        elif percent_bytes_saved == 0:
            msg += "Evened out"
        else:
            msg = "Lost"
        natural_saved = naturalsize(bytes_saved)
        msg += f" a total of {natural_saved} or {percent_bytes_saved:.2f}%"
        cprint(msg)
        if self._config.test:
            cprint("Test run did not change any files.")

    def report(self) -> None:
        """Report the total number and percent of bytes saved."""
        if self._config.verbose == 1:
            cprint("")
        if self.bytes_in:
            self._report_bytes_in()
        elif self._config.verbose:
            cprint("Didn't optimize any files.")

        if self.errors:
            cprint("Errors with the following files:", "red")
            for rs in self.errors:
                rs.report()
