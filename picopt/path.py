"""Data classes."""
from dataclasses import dataclass
from os import stat_result
from pathlib import Path

from confuse import AttrDict


@dataclass
class PathInfo:
    """Path Info object, mostly for passing down walk."""

    path: Path
    top_path: Path
    container_mtime: float | None
    convert: bool
    is_case_sensitive: bool
    stat: stat_result | None = None


def is_path_ignored(config: AttrDict, path: Path):
    """Match path against the ignore list."""
    return any(path.match(ignore_glob) for ignore_glob in config.ignore)
