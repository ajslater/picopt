"""Queue tasks."""
from dataclasses import dataclass, field
from pathlib import Path

from picopt.handlers.container import ContainerHandler
from picopt.stats import ReportStats


@dataclass
class DirResult:
    """Results from a directory."""

    path: Path
    results: list


@dataclass
class ContainerResult(DirResult):
    """Results from a container."""

    handler: ContainerHandler


@dataclass
class DirCompleteTask:
    """Task to compact timestamps."""

    path: Path


@dataclass
class ContainerCompleteTask:
    """Task to fire off repack once all container optimizations are done."""

    handler: ContainerHandler


@dataclass
class Totals:
    """Totals for final report."""

    bytes_in: int = 0
    bytes_out: int = 0
    errors: list[ReportStats] = field(default_factory=list)
