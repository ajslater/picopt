"""Bundles Stats + ProgressContext so the scheduler has a single sink."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from picopt.log import console
from picopt.log.progress import ProgressContext
from picopt.log.styles import MARKS
from picopt.log.summary import Stats

if TYPE_CHECKING:
    from picopt.report import ReportStats

__all__ = ("Reporter",)


@dataclass(slots=True)
class Reporter:
    """
    Aggregates run-level reporting sinks.

    Defaults give a no-op progress and a detached Stats instance so
    callers can construct a Reporter without wiring the full run plumbing
    (used in tests and pre-progress setup).
    """

    stats: Stats = field(default_factory=Stats)
    progress: ProgressContext = field(default_factory=ProgressContext)
    verbose: int = 0

    def record_report(self, report: ReportStats) -> None:
        """Record a finished file's outcome — log + count + advance."""
        if report.exc is not None:
            self.stats.record_error(report.path, str(report.exc))
            self.progress.mark_error()
            self._print_outcome(report.report_text(), "error")
            return

        bytes_out = (
            report.bytes_out
            if report.saved > 0 and not report.bigger
            else report.bytes_in
        )
        self.stats.record_bytes(report.bytes_in, bytes_out)

        kind = self._classify(report)
        path = report.path
        if path is not None:
            recorder = getattr(self.stats, f"record_{kind}", None)
            if recorder is not None:
                recorder(path)

        getattr(self.progress, f"mark_{kind}")()
        self._print_outcome(report.report_text(), kind)

    @staticmethod
    def _classify(report: ReportStats) -> str:
        if report.test:
            return "dry_run"
        if report.saved > 0:
            return "converted" if report.converted else "saved"
        return "lost"

    def _print_outcome(self, text: str, kind: str) -> None:
        if self.verbose < 2:  # noqa: PLR2004
            return
        style = MARKS[kind].style
        console.print(f"[{style}]{text}[/{style}]", highlight=False, soft_wrap=True)
