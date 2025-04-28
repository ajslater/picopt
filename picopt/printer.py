"""Print Messages."""

from termcolor import cprint


class Printer:
    """Printing messages during walk and handling."""

    def __init__(self, verbose: int):
        """Initialize verbosity and flags."""
        self._verbose = verbose
        self._last_verbose_message = False

    def message(
        self, reason, color="white", attrs=None, *, force_verbose=False, end="\n"
    ):
        """Print a dot or skip message."""
        if self._verbose < 1:
            return
        if self._verbose == 1 and not force_verbose:
            cprint(".", color, attrs=attrs, end="")
            self._last_verbose_message = False
            return
        if not self._last_verbose_message:
            reason = "\n" + reason
            if end:
                self._last_verbose_message = True
        attrs = attrs if attrs else []
        cprint(reason, color, attrs=attrs, end=end)

    def skip_container(self, container_type: str, path: str):
        """Skip entire container."""
        color = "white"
        attrs = ["dark"]
        reason = f"{container_type} contents all skipped: {path}"
        self.message(reason, color, attrs)

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

    def optimize_container(self, path: str):
        """Declare that we're optiming contents."""
        if self._verbose == 1:
            cprint(f"Optimizing contents in {path}:")

    def start_operation(self, operation: str, path: str):
        """Scan archive start."""
        self.message(f"{operation} {path}...", force_verbose=True, end="")

    def scan_archive(self, path: str):
        """Scan archive start."""
        self.start_operation("Scanning archive", path)

    def done(self):
        """Operation done."""
        if self._verbose:
            cprint("done.")
            self._last_verbose_message = True

    def container_unpacking(self, path: str):
        """Start Unpacking Operation."""
        if self._verbose:
            self.start_operation("Unpacking", path)

    def container_repacking(self, path: str):
        """Start Repacking Operation."""
        if self._verbose:
            self.start_operation("Repacking", path)

    def warn(self, message: str, exc: Exception | None = None):
        """Warning."""
        message = "WARNING: " + message
        if exc:
            message += f": {exc}"
        self.message(message, color="yellow", force_verbose=True)

    def error(self, message: str, exc: Exception):
        """Error."""
        message = "ERROR: " + message + f": {exc}"
        self.message(message, color="red", force_verbose=True)
