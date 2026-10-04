"""Print the doctor's rows, sections and summary."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from rich.table import Table
from rich.text import Text

from picopt.doctor.result import (
    DETAIL_STYLES,
    FAIL,
    OK,
    PROBLEMS,
    STATUS_MARKS,
    WARN,
    CheckResult,
    plural,
)
from picopt.log import console

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

SECTION_STYLE: Final = "bold yellow"
_NAME_STYLE: Final = "bold cyan"
_FIX_STYLE: Final = "dim"
_NAME_WIDTH: Final = 16


def _grid() -> Table:
    grid = Table.grid(padding=(0, 1))
    grid.add_column(width=1)  # indent
    grid.add_column(width=4, no_wrap=True)
    # Paths and exception messages are long unbroken words: fold them
    # rather than cut them off.
    grid.add_column(min_width=_NAME_WIDTH, overflow="fold")
    grid.add_column(overflow="fold")
    return grid


def visible(
    results: Iterable[CheckResult], *, problems_only: bool
) -> tuple[CheckResult, ...]:
    """Return the rows a report shows: every row, or only WARN and FAIL."""
    if not problems_only:
        return tuple(results)
    return tuple(result for result in results if result.status in PROBLEMS)


def render_heading(title: str) -> None:
    """Print a section heading."""
    # Text, not markup: titles can be user paths with brackets in them.
    console.print(Text(title, SECTION_STYLE))


def render_rows(results: Sequence[CheckResult]) -> None:
    """Print rows, each fix beneath its row."""
    if not results:
        return
    grid = _grid()
    for result in results:
        mark = STATUS_MARKS[result.status]
        grid.add_row(
            "",
            Text(mark.char, mark.style),
            Text(result.name, _NAME_STYLE),
            Text(result.detail, DETAIL_STYLES[result.status]),
        )
        if result.fix:
            grid.add_row("", "", "", Text(result.fix, _FIX_STYLE))
    console.print(grid)


def render_section(
    title: str, results: Sequence[CheckResult], *, problems_only: bool
) -> None:
    """Print a section; with problems_only, only if it has a problem row."""
    shown = visible(results, problems_only=problems_only)
    if problems_only and not shown:
        return
    render_heading(title)
    render_rows(shown)
    if not problems_only:
        console.print()


def render_summary(results: Iterable[CheckResult], extra: str = "") -> None:
    """Print the problem and warning counts, then any extra clause."""
    statuses = [result.status for result in results]
    fails = statuses.count(FAIL)
    warns = statuses.count(WARN)
    problems = plural(fails, "problem") if fails else "no problems"
    text = Text.assemble(
        ("Summary: ", "bold"),
        (problems, STATUS_MARKS[FAIL if fails else OK].style),
        ", ",
        (plural(warns, "warning"), STATUS_MARKS[WARN].style if warns else ""),
    )
    if extra:
        text.append(f" · {extra}")
    text.append(".")
    console.print(text)
