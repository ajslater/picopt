"""Data classes."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PathInfo:
    """Path Info object, mostly for passing down walk."""

    path: Path
    top_path: Path
    container_mtime: Optional[float]
    convert: bool
    is_case_sensitive: bool


@dataclass
class ReportInfo:
    """Info for Reports."""

    path: Path
    convert: bool
    test: bool
    bytes_in: int = 0
    bytes_out: int = 0
    exc: Optional[Exception] = None
