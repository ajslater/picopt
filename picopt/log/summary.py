"""End-of-run summary statistics and rendering."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from humanize import naturalsize
from rich.table import Table

from picopt.log.styles import MARKS

if TYPE_CHECKING:
    from pathlib import Path

    from rich.console import Console

__all__ = ("Stats", "render")


@dataclass(slots=True)
class Stats:
    """Thread-safe counters and itemized lists for the end-of-run summary."""

    # Mode flags set once at construction so the summary table can hide
    # rows that are irrelevant to this run.
    timestamps_active: bool = False
    dry_run_active: bool = False

    skipped: int = 0
    skipped_timestamp: int = 0
    copied: int = 0

    saved: list[Path] = field(default_factory=list)
    converted: list[Path] = field(default_factory=list)
    lost: list[Path] = field(default_factory=list)
    dry_run: list[Path] = field(default_factory=list)
    warnings: list[tuple[Path | None, str]] = field(default_factory=list)
    errors: list[tuple[Path | None, str]] = field(default_factory=list)

    bytes_in: int = 0
    bytes_out: int = 0

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_skipped(self) -> None:
        """Increment the skipped counter."""
        with self._lock:
            self.skipped += 1

    def record_skipped_timestamp(self) -> None:
        """Increment the timestamp-skipped counter."""
        with self._lock:
            self.skipped_timestamp += 1

    def record_copied(self) -> None:
        """Increment the archive-copy counter."""
        with self._lock:
            self.copied += 1

    def record_saved(self, path: Path) -> None:
        """Append a successfully-optimized file path."""
        with self._lock:
            self.saved.append(path)

    def record_converted(self, path: Path) -> None:
        """Append a successfully-converted file path."""
        with self._lock:
            self.converted.append(path)

    def record_lost(self, path: Path) -> None:
        """Append a file whose optimization was discarded for being larger."""
        with self._lock:
            self.lost.append(path)

    def record_dry_run(self, path: Path) -> None:
        """Append a path that would have been optimized (dry-run)."""
        with self._lock:
            self.dry_run.append(path)

    def record_warning(self, path: Path | None, message: str) -> None:
        """Append a warning tied to a file."""
        with self._lock:
            self.warnings.append((path, message))

    def record_error(self, path: Path | None, message: str) -> None:
        """Append an error tied to a file."""
        with self._lock:
            self.errors.append((path, message))

    def record_bytes(self, bytes_in: int, bytes_out: int) -> None:
        """Add to the run-level byte totals."""
        with self._lock:
            self.bytes_in += bytes_in
            self.bytes_out += bytes_out


def _counts_table(stats: Stats) -> Table:
    """
    Build the Counts table for the summary.

    Row styles match the per-event color scheme used by the loguru sink
    and the progress bar's CharStreamColumn so the same outcome reads
    the same way everywhere.
    """
    table = Table(title="Summary", show_header=False, title_style="bold")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Skipped", str(stats.skipped), style=MARKS["skipped"].style)
    if stats.timestamps_active:
        table.add_row(
            "Skipped (timestamp)",
            str(stats.skipped_timestamp),
            style=MARKS["skipped_timestamp"].style,
        )
    if stats.copied:
        table.add_row(
            "Copied unchanged", str(stats.copied), style=MARKS["copied"].style
        )
    table.add_row("Saved", str(len(stats.saved)), style=MARKS["saved"].style)
    if stats.converted:
        table.add_row(
            "Converted", str(len(stats.converted)), style=MARKS["converted"].style
        )
    if stats.lost:
        table.add_row("Lost", str(len(stats.lost)), style=MARKS["lost"].style)
    if stats.dry_run_active:
        table.add_row(
            "Would optimize (dry run)",
            str(len(stats.dry_run)),
            style=MARKS["dry_run"].style,
        )
    if stats.warnings:
        table.add_row(
            "Warnings", str(len(stats.warnings)), style=MARKS["warning"].style
        )
    if stats.errors:
        table.add_row("Errors", str(len(stats.errors)), style=MARKS["error"].style)
    return table


def _print_pairs(
    console: Console,
    header: str,
    pairs: list[tuple[Path | None, str]],
    style: str = "",
) -> None:
    if not pairs:
        return
    console.print(f"[bold]{header}:[/bold]")
    for path, message in pairs:
        line = f"  - {path}: {message}" if path else f"  - {message}"
        console.print(f"[{style}]{line}[/{style}]" if style else line, highlight=False)


def _bytes_summary(stats: Stats, *, dry_run: bool) -> str:
    if not stats.bytes_in:
        return "Didn't optimize any files."
    bytes_saved = stats.bytes_in - stats.bytes_out
    percent_saved = bytes_saved / stats.bytes_in * 100
    sign = (percent_saved > 0) - (percent_saved < 0)
    if dry_run:
        verbs = {1: "Could save", 0: "Could even out for", -1: "Could lose"}
    else:
        verbs = {1: "Saved", 0: "Evened out", -1: "Lost"}
    natural = naturalsize(abs(bytes_saved))
    return f"{verbs[sign]} a total of {natural} or {abs(percent_saved):.2f}%"


def render(stats: Stats, console: Console, *, dry_run: bool = False) -> None:
    """Print the summary to the given Rich console."""
    console.print(_counts_table(stats))
    _print_pairs(console, "Warnings", stats.warnings, MARKS["warning"].style)
    _print_pairs(console, "Errors", stats.errors, MARKS["error"].style)
    summary_line = _bytes_summary(stats, dry_run=dry_run)
    console.print(summary_line, highlight=False)
    if dry_run:
        console.print("Dry run did not change any files.", highlight=False)
