"""Rich Progress bar with a streaming per-file char column."""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from typing import TYPE_CHECKING, Final

from rich.progress import (
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text
from typing_extensions import Self, override

from picopt.log.styles import MARKS

if TYPE_CHECKING:
    from types import TracebackType

    from rich.console import Console
    from rich.progress import Task

__all__ = (
    "CharStreamColumn",
    "ProgressContext",
    "make_progress",
)


# Marks that count as a finished file and advance the bar.
_FILE_MARKS: Final = frozenset(
    {
        "skipped",
        "skipped_timestamp",
        "copied",
        "lost",
        "dry_run",
        "saved",
        "converted",
        "consumed_timestamp",
        "error",
    }
)


class CharStreamColumn(ProgressColumn):
    """A column that shows the most-recent action chars as a streaming Text."""

    def __init__(self, max_width: int = 40) -> None:
        """Initialize the deque ring per task."""
        super().__init__()
        self._max_width = max_width
        self._streams: dict[int, deque[tuple[str, str]]] = defaultdict(
            lambda: deque(maxlen=self._max_width)
        )
        self._lock = threading.Lock()

    def push(self, task_id: int, char: str, style: str) -> None:
        """Append a styled char to ``task_id``'s ring."""
        with self._lock:
            self._streams[task_id].append((char, style))

    @override
    def render(self, task: Task) -> Text:
        """Render the ring for ``task`` as a Rich Text."""
        text = Text()
        with self._lock:
            stream = list(self._streams.get(task.id, ()))
        for char, style in stream:
            text.append(char, style=style)
        return text


class ProgressContext:
    """
    Owns the Progress and the single TaskID; provides mark_* helpers.

    When ``enabled=False`` (no TTY, ``--quiet``, or unit tests) every
    mark_*/__enter__/__exit__ is a no-op so callers can hold a
    ProgressContext unconditionally.
    """

    def __init__(
        self,
        progress: Progress | None = None,
        char_column: CharStreamColumn | None = None,
        task_id: TaskID | None = None,
        *,
        enabled: bool = False,
    ) -> None:
        """Initialize."""
        self._progress = progress
        self._char_column = char_column
        self._task_id: TaskID | None = task_id
        self._enabled = enabled

    def __enter__(self) -> Self:
        """Enter the underlying live progress region (no-op when disabled)."""
        if self._enabled and self._progress is not None:
            self._progress.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the underlying live progress region (no-op when disabled)."""
        if self._enabled and self._progress is not None:
            self._progress.__exit__(exc_type, exc_val, exc_tb)

    def _mark(self, kind: str) -> None:
        if (
            not self._enabled
            or self._progress is None
            or self._char_column is None
            or self._task_id is None
        ):
            return
        mark = MARKS[kind]
        self._char_column.push(int(self._task_id), mark.char, mark.style)
        if kind in _FILE_MARKS:
            self._progress.advance(self._task_id, 1)

    def mark_skipped(self) -> None:
        """Mark a file as skipped (ignored, not handled, etc.)."""
        self._mark("skipped")

    def mark_skipped_timestamp(self) -> None:
        """Mark a file as skipped because its timestamp is older than recorded."""
        self._mark("skipped_timestamp")

    def mark_copied(self) -> None:
        """Mark archive contents copied through unchanged."""
        self._mark("copied")

    def mark_lost(self) -> None:
        """Mark a file whose optimized result was bigger than the original."""
        self._mark("lost")

    def mark_dry_run(self) -> None:
        """Mark a file as no-op on dry run."""
        self._mark("dry_run")

    def mark_saved(self) -> None:
        """Mark a successfully optimized file (smaller than original)."""
        self._mark("saved")

    def mark_converted(self) -> None:
        """Mark a successfully converted file."""
        self._mark("converted")

    def mark_packed(self) -> None:
        """Mark a file packed into an archive."""
        self._mark("packed")

    def mark_consumed_timestamp(self) -> None:
        """Mark a timestamp consumed from inside an archive."""
        self._mark("consumed_timestamp")

    def mark_warning(self) -> None:
        """Mark a non-fatal issue (no bar advance)."""
        self._mark("warning")

    def mark_error(self) -> None:
        """Mark a fatal error processing a file."""
        self._mark("error")


def make_progress(
    console: Console,
    *,
    enabled: bool = True,
    total: int | None = None,
    description: str = "Optimizing",
) -> ProgressContext:
    """Build a ProgressContext, or a no-op when disabled / not a terminal."""
    if not enabled or not console.is_terminal:
        return ProgressContext(enabled=False)

    # Size the streaming-char column so the whole bar fits on one line.
    # If the bar wraps, Rich's Live region flips into multi-line mode
    # and emits `\n` per refresh — which scrolls each frame past instead
    # of redrawing in place.
    #
    # Reserve ~46 chars for the other columns:
    #   spinner(~2) + " Optimizing "(12) + counts(~12) + time(~12) +
    #   inter-column spaces. Cap the stream at 40 on very wide terminals.
    char_width = max(8, min(40, console.width - 46))
    char_column = CharStreamColumn(max_width=char_width)
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        char_column,
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )
    task_id = progress.add_task(description, total=total)
    return ProgressContext(progress, char_column, task_id, enabled=True)
