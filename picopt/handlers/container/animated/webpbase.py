"""Animated Webp Base Class."""

from abc import ABC
from pathlib import Path
from tempfile import mkdtemp

from picopt.handlers.container.animated import ImageAnimated


class WebpAnimatedBase(ImageAnimated, ABC):
    """Base class for WebpAnimated Images."""

    def set_working_dir(self, identifier_suffix: str):
        """Return a working directory with a custom suffix."""
        working_path = self.get_working_path(identifier_suffix)
        suffix = str(hash(str(working_path.parent))) + "-"
        suffix += str(working_path.name)
        self.working_tmp_dir = Path(mkdtemp(suffix=suffix))

    def get_working_id(self):
        """Return the chief program name."""
        return self.PROGRAMS[0][0]
