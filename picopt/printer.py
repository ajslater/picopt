"""Print Messages."""

from pathlib import Path

from termcolor import cprint

from picopt.path import PathInfo


class Printer:
    """Printing messages during walk and handling."""

    def __init__(self, verbose: int) -> None:
        """Initialize verbosity and flags."""
        self._verbose: int = verbose
        self._after_newline: bool = True

    def _message(
        self,
        message: str,
        color: str = "white",
        attrs: list[str] | None = None,
        end: str = "\n",
        *,
        force_verbose: bool = False,
        force_continue_line: bool = False,
    ) -> None:
        """Print a dot or skip message."""
        if self._verbose < 1:
            return
        if not message:
            reason = "No message given to printer"
            raise ValueError(reason)
        if self._verbose == 1 and not force_verbose:
            message = "."
            end = ""
        elif not self._after_newline and not force_continue_line:
            message = "\n" + message
        attrs = attrs or []
        cprint(message, color, attrs=attrs, end=end, flush=True)
        self._after_newline = bool(end)

    def config(self, message: str) -> None:
        """Config messages."""
        self._message(message, color="cyan", force_verbose=True)

    def skip(
        self,
        reason,
        path_info: PathInfo,
        color: str = "dark_grey",
        attrs: list[str] | None = None,
    ) -> None:
        """Skip Message."""
        parts = ("Skip", reason, path_info.full_output_name())
        message = ": ".join(parts)
        self._message(message, color=color, attrs=attrs)

    def skip_container(self, container_type: str, path_info: PathInfo) -> None:
        """Skip entire container."""
        reason = f"{container_type}, contents all skipped"
        self.skip(reason, path_info)

    def skip_timestamp(self, message, path_info: PathInfo) -> None:
        """Skipped by timestamp."""
        self.skip(message, path_info, color="light_green", attrs=["dark", "bold"])

    def start_operation(
        self, operation: str, path_info: PathInfo, *, force_newline: bool = True
    ) -> None:
        """Scan archive start."""
        path = path_info.full_output_name()
        if self._verbose == 1 and force_newline:
            self._after_newline = False
        self._message(f"{operation} {path}...", force_verbose=True, end="")

    def deleted(self, path: Path | str) -> None:
        """Print deleted message."""
        self._message(f"Deleted {path}", color="yellow")

    def consumed_timestamp(self, path: Path | str) -> None:
        """Consume timestamp message."""
        self._message(f"Consumed picopt timestamp in archive: {path}", color="magenta")

    def scan_archive(self, path_info: PathInfo) -> None:
        """Scan archive start."""
        self.start_operation("Scanning archive", path_info)

    def container_unpacking(self, path_info: PathInfo) -> None:
        """Start Unpacking Operation."""
        # this fixes containers within containers newlines.
        self._after_newline = False
        self.start_operation("Unpacking", path_info)

    def container_repacking(self, path_info: PathInfo) -> None:
        """Start Repacking Operation."""
        if self._verbose > 1:
            self.start_operation("Repacking", path_info)

    def img2webp_repacking(self, path_info: PathInfo) -> None:
        """Start img2webp Repacking Operation."""
        if self._verbose > 1:
            self.start_operation(
                "Optimizing while repacking animated WebP...", path_info
            )

    def container_repacking_done(self) -> None:
        """Only done for repack if very verbose."""
        if self._verbose > 1:
            self.done()

    def copied(self) -> None:
        """Dot for copied file."""
        self._message(".", color="green", end="", force_continue_line=True)

    def optimize_container(self, path_info: PathInfo) -> None:
        """Declare that we're optimizing contents."""
        self.start_operation("Optimizing contents in", path_info, force_newline=False)

    def packed(self) -> None:
        """Dot for repacked file."""
        self._message(".", color="light_grey", end="", force_continue_line=True)

    def done(self) -> None:
        """Operation done."""
        self._message("done.", force_verbose=True, force_continue_line=True)

    def saved(self, report: str) -> None:
        """Report saved size."""
        self._message(report)

    def converted(self, report: str) -> None:
        """Report converted file."""
        self._message(report, color="light_cyan")

    def lost(self, report: str) -> None:
        """Lost size."""
        self._message(report, color="light_blue")

    def warn(self, message: str, exc: Exception | None = None) -> None:
        """Warning."""
        message = "WARNING: " + message
        if exc:
            message += f": {exc}"
        self._message(message, color="light_yellow", force_verbose=True)

    def error(self, message: str, exc: Exception) -> None:
        """Error."""
        message = "ERROR: " + message + f": {exc}"
        self._message(message, color="light_red", force_verbose=True)

    def error_title(self, message: str) -> None:
        """Error title."""
        self._message(message, color="light_red", force_verbose=True)

    def final_message(self, message: str) -> None:
        """Print final message."""
        self._message(message, force_verbose=True)
