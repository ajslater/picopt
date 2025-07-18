"""Walk initialization."""

from multiprocessing.pool import Pool
from typing import TYPE_CHECKING

from confuse.templates import AttrDict
from treestamps import Grovestamps, GrovestampsConfig

from picopt import PROGRAM_NAME
from picopt.config.consts import TIMESTAMPS_CONFIG_KEYS
from picopt.exceptions import PicoptError
from picopt.old_timestamps import OldTimestamps
from picopt.printer import Printer
from picopt.report import Totals
from picopt.walk.skip import WalkSkipper

if TYPE_CHECKING:
    from pathlib import Path


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
        self._config: AttrDict = config
        top_paths = []
        paths: list[Path] = sorted(frozenset(self._config.paths))
        for path in paths:
            if path.is_symlink() and not self._config.symlinks:
                continue
            top_paths.append(path)
        self._top_paths: tuple[Path, ...] = tuple(top_paths)
        self._validate_top_paths()
        self._printer: Printer = Printer(config.verbose)
        self._totals: Totals = Totals(config, self._printer)
        self._pool: Pool = Pool(self._config.jobs) if self._config.jobs else Pool()
        self._timestamps: Grovestamps | None = None  # reassigned at start of run
        self._skipper: WalkSkipper = WalkSkipper(config, self._printer)

    def _init_timestamps(self) -> None:
        """Init timestamps."""
        if not self._config.timestamps:
            return
        config = GrovestampsConfig(
            paths=self._top_paths,
            program_name=PROGRAM_NAME,
            verbose=self._config.verbose,
            symlinks=self._config.symlinks,
            ignore=self._config.ignore,
            check_config=self._config.timestamps_check_config,
            program_config=self._config,
            program_config_keys=TIMESTAMPS_CONFIG_KEYS,
        )
        self._timestamps = Grovestamps(config)
        for timestamps in self._timestamps.values():
            OldTimestamps(self._config, timestamps).import_old_timestamps()
        self._skipper.set_timestamps(self._timestamps)
