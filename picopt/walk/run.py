"""Walk the directory trees and files and call the optimizers."""

from termcolor import cprint
from treestamps import Grovestamps, GrovestampsConfig, Treestamps

from picopt import PROGRAM_NAME
from picopt.config.consts import TIMESTAMPS_CONFIG_KEYS
from picopt.old_timestamps import OldTimestamps
from picopt.path import PathInfo
from picopt.stats import Totals
from picopt.walk.walk import WalkWalkers


class Walk(WalkWalkers):
    """Walk object for storing state of a walk run."""

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

    def run(self) -> Totals:
        """Optimize all configured files."""
        self._init_timestamps()

        # Walk each top file
        top_results = {}
        for top_path in self._top_paths:
            dirpath = Treestamps.get_dir(top_path)
            path_info = PathInfo(
                dirpath,
                convert=True,
                path=top_path,
            )
            result = self.walk_file(path_info)
            if not result:
                continue
            if dirpath not in top_results:
                top_results[dirpath] = []
            top_results[dirpath].append(result)

        # Finish
        for dirpath, results in top_results.items():
            self._finish_results(results, dirpath, in_container=False)

        # Shut down multiprocessing
        self._pool.close()
        self._pool.join()

        cprint("done.")

        if self._timestamps:
            self._timestamps.dumpf()

        return self._totals
