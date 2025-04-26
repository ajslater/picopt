"""Print Messages."""

from termcolor import cprint


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
