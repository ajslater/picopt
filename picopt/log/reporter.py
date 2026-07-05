"""Bundles Stats + ProgressContext so the scheduler has a single sink."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from picopt.log import console
from picopt.log.progress import ProgressContext
from picopt.log.styles import MARKS
from picopt.log.summary import Stats

if TYPE_CHECKING:
    from pathlib import Path

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
        self._record_kind(kind, report.path)
        self._print_outcome(report.report_text(), kind)

    def _record_kind(self, kind: str, path: Path | None) -> None:
        """Dispatch to the explicit sink pair for a classified outcome."""
        match kind:
            case "dry_run":
                if path is not None:
                    self.stats.record_dry_run(path)
                self.progress.mark_dry_run()
            case "converted":
                if path is not None:
                    self.stats.record_converted(path)
                self.progress.mark_converted()
            case "saved":
                if path is not None:
                    self.stats.record_saved(path)
                self.progress.mark_saved()
            case "lost":
                if path is not None:
                    self.stats.record_lost(path)
                self.progress.mark_lost()
            case _:
                msg = f"Unknown report outcome kind: {kind}"
                raise ValueError(msg)

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
