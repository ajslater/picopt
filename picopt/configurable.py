"""Abstract class to hold config and match ignores."""
from abc import ABC
from pathlib import Path

from confuse import AttrDict


class Configurable(ABC):
    """Match ignore paths."""

    def __init__(self, config: AttrDict) -> None:
        """Initialize."""
        self._config: AttrDict = config

    def is_path_ignored(self, path: Path):
        """Match path against the ignore listg."""
        for ignore_glob in self._config.ignore:
            if path.match(ignore_glob):
                return True
        return False
