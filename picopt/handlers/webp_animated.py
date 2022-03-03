"""WebP Animated images are treated like containers."""
from pathlib import Path
from typing import Optional

from PIL import Image

from picopt.handlers.container import ContainerHandler
from picopt.handlers.handler import Format
from picopt.handlers.webp import WebP


class WebPAnimated(ContainerHandler):
    """Animated WebP container."""

    OUTPUT_FORMAT: str = WebP.OUTPUT_FORMAT
    OUTPUT_FORMAT_OBJ = Format(OUTPUT_FORMAT, False, True)
    PROGRAMS = ("webpmux", "img2webp")

    _WEBPMUX_ARGS_PREFIX = ("webpmux", "-get", "frame")
    _IMG2WEBP_ARGS_PREFIX = ("img2webp", "-min_size")
    _WEBPMUX_EXIF_ARGS_PREFIX = ("webpmux", "-set", "exif")

    @classmethod
    def identify_format(cls, _path: Path) -> Optional[Format]:
        """Return the format if this handler can handle this path."""
        raise NotImplementedError()

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

    def create_container(self, working_path: Path) -> None:
        """Remux the optimized frames into an animated webp."""
        frames = sorted([str(path) for path in self.tmp_container_dir.iterdir()])
        args = [
            *self._IMG2WEBP_ARGS_PREFIX,
            *frames,
            "-o",
            str(working_path),
        ]
        self.run_ext(tuple(args))
        if not self.config.destroy_metadata and self.exif:
            self._set_exif(working_path)

    def _set_exif(self, working_path):
        """Set the exif data on the rebuilt image."""
        if not self.exif:
            return

        # dump exif
        exif_path = working_path.with_suffix(".exif")
        with exif_path.open("wb") as exif:
            exif.write(self.exif.tobytes())
        self.working_paths.add(exif_path)

        # move working file
        container_exif_working_path = self.get_working_path("exif")
        working_path.replace(container_exif_working_path)
        self.working_paths.add(container_exif_working_path)

        # run exif set
        args = (
            *self._WEBPMUX_EXIF_ARGS_PREFIX,
            str(exif_path),
            str(container_exif_working_path),
            "-o",
            str(working_path),
        )
        self.run_ext(args)
