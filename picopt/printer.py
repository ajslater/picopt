"""Print Messages."""

from pathlib import Path

from termcolor import cprint

from picopt.path import PathInfo


class Printer:
    """Printing messages during walk and handling."""

    def __init__(self, verbose: int):
        """Initialize verbosity and flags."""
        self._verbose = verbose
        self._last_verbose_message = True

    def message(
        self, reason, color="white", attrs=None, *, force_verbose=False, end="\n"
    ):
        """Print a dot or skip message."""
        if self._verbose < 1:
            return
        if (self._verbose == 1 and not force_verbose) or not reason:
            cprint(".", color, attrs=attrs, end="", flush=True)
            self._last_verbose_message = False
            return
        if not self._last_verbose_message:
            reason = "\n" + reason
        attrs = attrs if attrs else []
        cprint(reason, color, attrs=attrs, end=end, flush=True)
        if end:
            self._last_verbose_message = True

    def skip_message(self, message):
        """Skip Message."""
        self.message(message, color="dark_grey")

    def skip_container(self, container_type: str, path_info: PathInfo):
        """Skip entire container."""
        path = path_info.full_output_name()
        reason = f"{container_type} contents all skipped: {path}"
        self.skip_message(reason)

    def skip_timestamp_message(self, message):
        """Skipped by timestamp."""
        self.message(message, color="light_green", attrs=["dark", "bold"])

    def start_operation(self, operation: str, path_info: PathInfo):
        """Scan archive start."""
        path = path_info.full_output_name()
        self.message(f"{operation} {path}...", force_verbose=True, end="")

    def message_deleted(self, path: Path | str):
        """Print deleted message."""
        self.message(f"Deleted {path}", color="yellow")

    def message_consumed_timestamp(self, path: Path | str):
        """Consume timestamp message."""
        self.message(f"Consumed picopt timestamp in archive: {path}", color="magenta")

    def scan_archive(self, path_info: PathInfo):
        """Scan archive start."""
        self.start_operation("Scanning archive", path_info)

    def container_unpacking(self, path_info: PathInfo):
        """Start Unpacking Operation."""
        # this fixes containers within containers newlines.
        self._last_verbose_message = False
        self.start_operation("Unpacking", path_info)

    def container_repacking(self, path_info: PathInfo):
        """Start Repacking Operation."""
        if self._verbose > 1:
            self.start_operation("Repacking", path_info)

    def container_repacking_done(self):
        """Only done for repack if very verbose."""
        if self._verbose > 1:
            self.done()

    def copied_message(self):
        """Dot for copied file."""
        self.message("", color="green")

    def optimize_container(self, path_info: PathInfo):
        """Declare that we're optimizing contents."""
        path = path_info.full_output_name()
        cprint(f"Optimizing contents in {path}:")

    def packed_message(self):
        """Dot for repacked file."""
        self.message("", color="light_grey")

    def done(self):
        """Operation done."""
        if self._verbose:
            cprint("done.")
            self._last_verbose_message = True

    def saved_message(self, report):
        """Report saved size."""
        self.message(report, color="light_cyan")

    def lost_message(self, report):
        """Lost size."""
        self.message(report, color="light_blue")

    def warn(self, message: str, exc: Exception | None = None):
        """Warning."""
        message = "WARNING: " + message
        if exc:
            message += f": {exc}"
        self.message(message, color="light_yellow", force_verbose=True)

    def error(self, message: str, exc: Exception):
        """Error."""
        message = "ERROR: " + message + f": {exc}"
        self.message(message, color="light_red", force_verbose=True)
