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


class Messenger:
    """Class for printing dots and skipped messages."""

    def __init__(self, verbose: int):
        """Initialize verbosity and flags."""
        self._verbose = verbose
        self._last_verbose_message = False

    def skip_message(self, reason, color="white", attrs=None):
        """Print a dot or skip message."""
        if self._verbose < 1:
            return
        if self._verbose == 1:
            cprint(".", color, attrs=attrs, end="")
            self._last_verbose_message = False
            return
        if not self._last_verbose_message:
            reason = "\n" + reason
            self._last_verbose_message = True
        attrs = attrs if attrs else []
        cprint(reason, color, attrs=attrs)

    def skip_container(self, container_type: str, path: str):
        """Skip entire container."""
        color = "white"
        attrs = ["dark"]
        reason = f"{container_type} contents all skipped: {path}"
        self.skip_message(reason, color, attrs)

    def handled_message(self):
        """Dot for handled file."""
        if self._verbose:
            cprint(".", end="")
            self._last_verbose_message = False

    def no_handler(self):
        """Dot for no handler."""
        if self._verbose:
            cprint(".", attrs=["dark"], end="")
            self._last_verbose_message = False

    def copied_message(self):
        """Dot for copied file."""
        if self._verbose:
            cprint(".", attrs=["dark"], end="")
            self._last_verbose_message = False

    def packed_message(self):
        """Dot for repacked file."""
        if self._verbose:
            cprint(".", end="")
            self._last_verbose_message = False


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
        self._messenger = Messenger(self._config.verbose)

    def set_timestamps(self, timestamps: Grovestamps):
        """Reset the timestamps after they've been established."""
        self._timestamps = timestamps

    def _is_skippable(self, path_info: PathInfo) -> bool:
        """Handle things that are not optimizable files."""
        reason = ""
        color = "white"
        attrs: list = ["dark"]

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
            reason = f"WARNING: {path_info.full_output_name()} not found."
            color = "yellow"
            attrs = []

        if reason:
            self._messenger.skip_message(reason, color, attrs)

        return bool(reason)

    def _clean_up_working_files(self, path: Path) -> None:
        """Auto-clean old working temp files if encountered."""
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
            reason = f"Deleted {path}"
            self._messenger.skip_message(reason, "yellow")
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
        color = "green"
        self._messenger.skip_message(reason, color)

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
