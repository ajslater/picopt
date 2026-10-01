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
from enum import StrEnum, auto
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = (
    "LEVEL_STYLES",
    "MARKS",
    "Mark",
    "MarkKind",
)


class MarkKind(StrEnum):
    """Per-event progress mark kinds; values are the lowercase names."""

    SKIPPED = auto()
    SKIPPED_TIMESTAMP = auto()
    COPIED = auto()
    LOST = auto()
    DRY_RUN = auto()
    SAVED = auto()
    CONVERTED = auto()
    PACKED = auto()
    CONSUMED_TIMESTAMP = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass(frozen=True, slots=True)
class Mark:
    """A single (char, Rich-style) pair for a per-event progress mark."""

    char: str
    style: str


# Per-outcome marks. Keys mirror the printer-method names they replace,
# so call sites read naturally (``progress.mark_saved()`` matches the old
# ``printer.saved(...)``).
MARKS: Final[Mapping[MarkKind, Mark]] = MappingProxyType(
    {
        # Per-file marks (advance the progress bar).
        MarkKind.SKIPPED: Mark(".", "bright_black"),
        MarkKind.SKIPPED_TIMESTAMP: Mark(".", "bright_green dim bold"),
        MarkKind.COPIED: Mark(".", "green"),
        MarkKind.LOST: Mark(".", "bright_blue bold"),
        MarkKind.DRY_RUN: Mark(".", "bright_black bold"),
        MarkKind.SAVED: Mark(".", "bright_white"),
        MarkKind.CONVERTED: Mark(".", "bright_cyan"),
        MarkKind.PACKED: Mark(".", "white"),
        MarkKind.CONSUMED_TIMESTAMP: Mark(".", "magenta"),
        MarkKind.WARNING: Mark("!", "bright_yellow"),
        MarkKind.ERROR: Mark("X", "bright_red"),
    }
)


def _style(kind: MarkKind) -> str:
    return MARKS[kind].style


# Loguru level → Rich style. Levels that correspond to a per-event mark
# share that mark's style so log lines and progress chars match.
LEVEL_STYLES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "DEBUG": _style(MarkKind.SKIPPED),
        "INFO": "cyan",
        "SUCCESS": _style(MarkKind.SAVED),
        "WARNING": _style(MarkKind.WARNING),
        "ERROR": _style(MarkKind.ERROR),
        "CRITICAL": _style(MarkKind.ERROR),
    }
)
