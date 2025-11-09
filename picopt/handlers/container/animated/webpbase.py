"""Animated Webp Base Class."""

from abc import ABC
from pathlib import Path
from tempfile import mkdtemp

from picopt.handlers.container.animated import ImageAnimated


class WebpAnimatedBase(ImageAnimated, ABC):
    """Base class for WebpAnimated Images."""

    def set_working_dir(self):
        """Return a working directory with a custom suffix."""
        working_path = self.get_working_path()
        suffix = str(hash(str(working_path.parent))) + "-"
        suffix += str(working_path.name)
        self.working_tmp_dir = Path(mkdtemp(suffix=suffix))

    def set_frame_index_width(self):
        """Set the frame index zfill width for frame filenames."""
        n_frames = self.info["n_frames"]
        self.frame_index_width = len(str(n_frames))

    def get_frame_path(self, index: int):
        """Get the frame temporary file path."""
        frame_num = str(index).zfill(self.frame_index_width)
        return self.working_tmp_dir / f"frame_{frame_num}.webp"
