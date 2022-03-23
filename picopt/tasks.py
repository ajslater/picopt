"""Queue tasks."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from picopt.handlers.container import ContainerHandler
from picopt.stats import ReportStats


@dataclass
class DirResult:
    """Results from a directory."""

    path: Path
    results: List


@dataclass
class DirCompactTask:
    """Task to compact timestamps."""

    path: Path


@dataclass
class ContainerDirResult(DirResult):
    """Results from a container."""

    handler: ContainerHandler


@dataclass
class ContainerRepackResult:
    """Task to fire off repack once all container optimizations are done."""

    handler: ContainerHandler


@dataclass
class Totals:
    """Totals for final report."""

    bytes_in: int = 0
    bytes_out: int = 0
    errors: List[ReportStats] = field(default_factory=list)
