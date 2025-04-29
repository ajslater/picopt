"""Walk Methods for checking and skipping."""

import shutil
from pathlib import Path

from confuse import AttrDict
from termcolor import cprint
from treestamps import Grovestamps, Treestamps

from picopt import PROGRAM_NAME
from picopt.handlers.handler import Handler
from picopt.old_timestamps import OLD_TIMESTAMPS_NAME
from picopt.path import PathInfo, is_path_ignored
from picopt.printer import Printer


class WalkSkipper:
    """Walk Methods for checking and skipping."""

    _TIMESTAMPS_FILENAMES = frozenset(
        {*Treestamps.get_filenames(PROGRAM_NAME), OLD_TIMESTAMPS_NAME}
    )

    def __init__(
        self,
        config: AttrDict,
        timestamps: Grovestamps | dict | None = None,
        *,
        in_archive: bool = False,
    ):
        """Initialize."""
        self._config = config
        self._timestamps = timestamps if timestamps else {}
        self._in_archive = in_archive
        self._printer = Printer(self._config.verbose)

    def set_timestamps(self, timestamps: Grovestamps):
        """Reset the timestamps after they've been established."""
        self._timestamps = timestamps

    def _log_skip(self, reason: str, *, warn: bool):
        if not reason:
            return
        if warn:
            self._printer.warn(reason)
        else:
            self._printer.skip_message(reason)

    def _is_skippable(self, path_info: PathInfo) -> bool:
        """Handle things that are not optimizable files."""
        reason = ""
        warn = False

        path = path_info.path

        # File types
        if not self._config.symlinks and path and path.is_symlink():
            reason = f"Skip symlink {path_info.full_output_name()}"
        elif path_info.name() in self._TIMESTAMPS_FILENAMES:
            legacy = "legacy " if path_info.name() == OLD_TIMESTAMPS_NAME else ""
            reason = f"Skip {legacy}timestamp {path_info.full_output_name()}"
        elif is_path_ignored(
            self._config,
            path_info.archive_psuedo_path(),
            ignore_case=path_info.is_case_sensitive,
        ):
            reason = f"Skip ignored {path_info.full_output_name()}"
        elif not self._in_archive and path and not path.exists():
            # Check disk last for performance
            reason = f"{path_info.full_output_name()} not found."
            warn = True

        self._log_skip(reason, warn=warn)

        return bool(reason)

    def _clean_up_working_files(self, path: Path) -> None:
        """Auto-clean old working temp files if encountered."""
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
            self._printer.message_deleted(path)
        except Exception as exc:
            cprint("\n" + str(exc), "red")
            self._last_verbose_message = True

    def is_walk_file_skip(
        self,
        path_info: PathInfo,
    ) -> bool:
        """Decide on skip the file or not."""
        if self._is_skippable(path_info):
            return True

        path = path_info.path
        if path and path.name.rfind(Handler.WORKING_SUFFIX) > -1:
            self._clean_up_working_files(path)
            return True
        return False

    def _skip_older_than_timestamp(self, path_info: PathInfo) -> None:
        """Report on skipping files older than the timestamp."""
        reason = f"Skip older than timestamp: {path_info.full_output_name()}"
        self._printer.skip_timestamp_message(reason)

    def _get_walk_after(self, path_info: PathInfo):
        if self._config.after is not None:
            walk_after = self._config.after
        elif path_info.archive_psuedo_path() and self._config.timestamps:
            timestamps = self._timestamps.get(path_info.top_path, {})
            walk_after = timestamps.get(path_info.archive_psuedo_path())
        else:
            walk_after = None
        return walk_after

    def is_older_than_timestamp(
        self,
        path_info: PathInfo,
    ) -> bool:
        """Is the file older than the timestamp."""
        walk_after = self._get_walk_after(path_info)
        if walk_after is None:
            return False

        mtime = path_info.mtime()
        if result := bool(mtime <= walk_after):
            self._skip_older_than_timestamp(path_info)
        return result
