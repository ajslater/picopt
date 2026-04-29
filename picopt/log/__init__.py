"""Loguru + Rich logging setup for picopt."""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Final

from loguru import logger
from rich.console import Console

from picopt.log.styles import LEVEL_STYLES

if TYPE_CHECKING:
    from loguru import Record

__all__ = ("console", "logger", "setup")

# Single Console for everything — both Rich Progress and the loguru sink
# share it so the live region and log lines stay in sync.
#
# `highlight=False` is critical: the default repr-highlighter would
# otherwise be applied to anything Rich re-prints internally, including
# the rendered ANSI strings produced by the live progress bar. On some
# installs that turns each `[` in `\x1b[Xm` sequences into a bold-styled
# bracket and leaves the leading `\x1b` as a stray byte, so the dots
# show up as literal `[2m[90m.[0m` text in the terminal.
console: Final[Console] = Console(highlight=False)


# verbose -> minimum loguru level to emit
_VERBOSE_LEVEL: Final = {
    0: "ERROR",
    1: "WARNING",
    2: "INFO",
}


def _verbose_to_level(verbose: int) -> str:
    if verbose <= 0:
        return "ERROR"
    return _VERBOSE_LEVEL.get(verbose, "DEBUG")


def _sink(message: object) -> None:
    """Write a loguru record to the shared Rich console."""
    record: Record = message.record  # pyright: ignore[reportAttributeAccessIssue]
    level = record["level"].name
    style = LEVEL_STYLES.get(level, "white")
    text = record["message"]
    console.print(f"[{style}]{text}[/{style}]", highlight=False, soft_wrap=True)


_configured = False


def setup(verbose: int) -> None:
    """Configure loguru for the given verbosity. Idempotent."""
    global _configured  # noqa: PLW0603
    if not _configured:
        # Already registered raises ValueError (e.g. test re-entry).
        with suppress(ValueError):
            logger.level("CONFIG", no=22, color="<cyan>")
        _configured = True

    logger.remove()
    if verbose > 0:
        logger.add(
            _sink,
            level=_verbose_to_level(verbose),
            format="{message}",
        )
