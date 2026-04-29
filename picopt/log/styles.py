"""
Centralized color / style / char definitions for picopt output.

Single source of truth for everything user-facing: the streaming-char
column on the progress bar, the loguru sink that writes log lines, the
end-of-run summary table, and the help-epilogue char-key legend.

Style choices intentionally mirror the old termcolor-based ``Printer``
so longtime users see the same colors for the same outcomes:

  termcolor name   →  Rich style
  ----------------    -----------------
  dark_grey        →  bright_black
  light_grey       →  white          (ANSI 37 — the "dim" white slot)
  white            →  bright_white   (ANSI 97 — the bright white slot)
  light_green      →  bright_green
  light_red        →  bright_red
  light_blue       →  bright_blue
  light_cyan       →  bright_cyan
  light_yellow     →  bright_yellow
  green / cyan / magenta / yellow → unchanged
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = (
    "LEVEL_STYLES",
    "MARKS",
    "Mark",
)


@dataclass(frozen=True, slots=True)
class Mark:
    """A single (char, Rich-style) pair for a per-event progress mark."""

    char: str
    style: str


# Per-outcome marks. Keys mirror the printer-method names they replace,
# so call sites read naturally (``progress.mark_saved()`` matches the old
# ``printer.saved(...)``).
MARKS: Final[Mapping[str, Mark]] = MappingProxyType(
    {
        # Per-file marks (advance the progress bar).
        "skipped": Mark(".", "bright_black"),
        "skipped_timestamp": Mark(".", "bright_green dim bold"),
        "copied": Mark(".", "green"),
        "lost": Mark(".", "bright_blue bold"),
        "dry_run": Mark(".", "bright_black bold"),
        "saved": Mark(".", "bright_white"),
        "converted": Mark(".", "bright_cyan"),
        "packed": Mark(".", "white"),
        "consumed_timestamp": Mark(".", "magenta"),
        "warning": Mark("!", "bright_yellow"),
        "error": Mark("X", "bright_red"),
    }
)


def _style(key: str) -> str:
    return MARKS[key].style


# Loguru level → Rich style. Levels that correspond to a per-event mark
# share that mark's style so log lines and progress chars match.
LEVEL_STYLES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "DEBUG": _style("skipped"),
        "INFO": "cyan",
        "SUCCESS": _style("saved"),
        "WARNING": _style("warning"),
        "ERROR": _style("error"),
        "CRITICAL": _style("error"),
    }
)
