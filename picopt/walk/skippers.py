"""Walk Methods for checking and skipping."""

import shutil
from pathlib import Path

from termcolor import cprint
from treestamps import Treestamps

from picopt import PROGRAM_NAME
from picopt.handlers.handler import Handler
from picopt.old_timestamps import OLD_TIMESTAMPS_NAME
from picopt.path import PathInfo, is_path_ignored
from picopt.walk.init import WalkInit


class WalkSkippers(WalkInit):
    """Walk Methods for checking and skipping."""

    _TIMESTAMPS_FILENAMES = frozenset(
        {*Treestamps.get_filenames(PROGRAM_NAME), OLD_TIMESTAMPS_NAME}
    )

    def _is_skippable(self, path_info: PathInfo) -> bool:
        """Handle things that are not optimizable files."""
        reason = None
        color = "white"
        attrs: list = ["dark"]

        # File types
        if path_info.archiveinfo and path_info.is_dir():
            reason = f"Skip archive directory {path_info.full_name()}"
        elif (
            not self._config.symlinks and path_info.path and path_info.path.is_symlink()
        ):
            reason = f"Skip symlink {path_info.full_name()}"
        elif path_info.name() in self._TIMESTAMPS_FILENAMES:
            legacy = "legacy " if path_info.name() == OLD_TIMESTAMPS_NAME else ""
            reason = f"Skip {legacy}timestamp {path_info.full_name()}"
        elif (
            not path_info.archiveinfo and path_info.path and not path_info.path.exists()
        ):
            reason = f"WARNING: {path_info.full_name()} not found."
            color = "yellow"
            attrs = []
        elif is_path_ignored(self._config, Path(path_info.name())):
            reason = f"Skip ignored {path_info.full_name()}"

        if reason and self._config.verbose > 1:
            cprint(reason, color, attrs=attrs)

        return bool(reason)

    def _is_older_than_timestamp(
        self,
        path_info: PathInfo,
    ) -> bool:
        """Is the file older than the timestamp."""
        if self._config.after is not None:
            walk_after = self._config.after
        elif path_info.path and self._config.timestamps:
            timestamps = self._timestamps.get(path_info.top_path, {})
            walk_after = timestamps.get(path_info.path)
        else:
            walk_after = None

        if walk_after is None:
            return False

        mtime = path_info.mtime()
        return bool(mtime <= walk_after)

    def _clean_up_working_files(self, path: Path) -> None:
        """Auto-clean old working temp files if encountered."""
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
            if self._config.verbose > 1:
                cprint(f"Deleted {path}", "yellow")
        except Exception as exc:
            cprint(str(exc), "red")

    def _skip_older_than_timestamp(self, path) -> None:
        """Report on skipping files older than the timestamp."""
        color = "green"
        if self._config.verbose == 1:
            cprint(".", color, end="")
        elif self._config.verbose > 1:
            cprint(f"Skip older than timestamp: {path}", color)

    def _is_walk_file_skip(
        self,
        path_info: PathInfo,
    ) -> bool:
        """Decide on skip the file or not."""
        if self._is_skippable(path_info):
            if self._config.verbose == 1:
                cprint(".", "white", attrs=["dark"], end="")
            return True

        path = path_info.path
        if path and path.name.rfind(Handler.WORKING_SUFFIX) > -1:
            self._clean_up_working_files(path)
            if self._config.verbose == 1:
                cprint(".", "yellow", end="")
            return True
        return False
