"""WebP Animated images are treated like containers."""
from pathlib import Path
from typing import List, Optional, Set

from PIL import Image

from picopt.handlers.container import ContainerHandler
from picopt.handlers.handler import Format
from picopt.handlers.webp import WebP


class WebPAnimated(ContainerHandler):
    """Animated WebP container."""

    FORMAT_STR: str = WebP.FORMAT_STR
    FORMAT = Format(FORMAT_STR, False, True)
    NATIVE_FORMATS: Set[Format] = set([FORMAT])
    IMPLIES_RECURSE: bool = True
    SUFFIX: str = "." + FORMAT_STR.lower()
    PROGRAMS = ("webpmux", "img2webp")

    _WEBPMUX_ARGS_PREFIX = ("webpmux", "-get", "frame")
    _IMG2WEBP_ARGS_PREFIX = ("img2webp", "-min_size")

    @classmethod
    def can_handle(cls, _path: Path) -> Optional[Format]:
        """Can the handler handle this file type."""
        # XXX This never gets called because image format is called earlier
        # format = cls.get_image_format(path)
        # if format in (cls.LOSSLESS_FORMAT, cls.LOSSY_FORMAT):
        #    return format
        return None

    def unpack_into(self) -> None:
        """Unpack webp into temp dir."""
        with Image.open(self.original_path) as image:
            n_frames = getattr(image, "n_frames", 1)
        for frame_index in range(0, n_frames):
            frame_path = self.tmp_container_dir / f"frame-{frame_index:08d}.webp"
            args = [
                *self._WEBPMUX_ARGS_PREFIX,
                str(frame_index),
                str(self.original_path),
                "-o",
                str(frame_path),
            ]
            self.run_ext(tuple(args))
        print(self.tmp_container_dir.iterdir())

    def create_container(self, working_path: Path) -> None:
        """Remux the optimized frames into an animated webp."""
        frames = sorted([str(path) for path in self.tmp_container_dir.iterdir()])
        args = [
            *self._IMG2WEBP_ARGS_PREFIX,
            *frames,
            "-o",
            str(working_path),
        ]
        print(args)
        self.run_ext(tuple(args))
