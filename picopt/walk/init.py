"""Walk initialization."""

from multiprocessing.pool import Pool
from typing import TYPE_CHECKING

from confuse.templates import AttrDict

from picopt.exceptions import PicoptError
from picopt.stats import Totals
from picopt.walk.skip import WalkSkipper

if TYPE_CHECKING:
    from pathlib import Path

    from treestamps import Grovestamps


class WalkInit:
    """Initialization."""

    def _validate_top_paths(self):
        """Init Run."""
        # Validate top_paths
        if not self._top_paths:
            msg = "No paths to optimize."
            raise PicoptError(msg)
        for path in self._top_paths:
            if not path.exists():
                msg = f"Path does not exist: {path}"
                raise PicoptError(msg)

    def __init__(self, config: AttrDict) -> None:
        """Initialize."""
        self._config = config
        top_paths = []
        paths: list[Path] = sorted(frozenset(self._config.paths))
        for path in paths:
            if path.is_symlink() and not self._config.symlinks:
                continue
            top_paths.append(path)
        self._top_paths: tuple[Path, ...] = tuple(top_paths)
        self._validate_top_paths()
        self._totals = Totals(config)
        if self._config.jobs:
            self._pool = Pool(self._config.jobs)
        else:
            self._pool = Pool()
        self._timestamps: Grovestamps | None = None  # reassigned at start of run
        self._skipper = WalkSkipper(config)
