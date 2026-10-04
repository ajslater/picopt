"""The doctor's result model: one row per check."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from picopt.log.styles import MARKS, Mark, MarkKind

if TYPE_CHECKING:
    from collections.abc import Mapping


class DoctorStatus(StrEnum):
    """
    How a row bears on the run.

    OFF means "not enabled"; picopt's progress marks already use "skip".
    INFO rows report without judging, and only the full report shows them.
    """

    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"
    OFF = "OFF"
    INFO = "INFO"


OK: Final = DoctorStatus.OK
WARN: Final = DoctorStatus.WARN
FAIL: Final = DoctorStatus.FAIL
OFF: Final = DoctorStatus.OFF
INFO: Final = DoctorStatus.INFO
PROBLEMS: Final[frozenset[DoctorStatus]] = frozenset({WARN, FAIL})

STATUS_MARKS: Final[Mapping[DoctorStatus, Mark]] = MappingProxyType(
    {
        OK: Mark("ok", "green"),
        WARN: Mark("WARN", MARKS[MarkKind.WARNING].style),
        FAIL: Mark("FAIL", MARKS[MarkKind.ERROR].style),
        OFF: Mark("off", MARKS[MarkKind.SKIPPED].style),
        INFO: Mark("", ""),
    }
)
# A failure's detail is plain red rather than the tag's bright red, so the
# tag stays the loudest thing on the line.
DETAIL_STYLES: Final[Mapping[DoctorStatus, str]] = MappingProxyType(
    {
        OK: "",
        WARN: STATUS_MARKS[WARN].style,
        FAIL: "red",
        OFF: STATUS_MARKS[OFF].style,
        INFO: "",
    }
)


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One row of the report."""

    section: str
    name: str
    status: DoctorStatus
    detail: str = ""
    # A command or edit that resolves the row, printed beneath it.
    fix: str = ""


def describe(exc: BaseException) -> str:
    """Exception text, prefixed with its type."""
    return f"{type(exc).__name__}: {exc}"


def plural(count: int, word: str, plural_word: str = "") -> str:
    """Count a word, e.g. "1 warning" or "2 entries"."""
    return f"{count} {word if count == 1 else plural_word or word + 's'}"
