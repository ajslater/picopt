"""WebP Animated images are treated like containers."""
from pathlib import Path
from typing import Optional

from PIL import Image, ImageSequence

from picopt.handlers.container import ContainerHandler
from picopt.handlers.handler import Format
from picopt.handlers.image import TIFF_ANIMATED_FORMAT_OBJ
from picopt.handlers.webp import WebP


class WebPAnimated(ContainerHandler):
    """Animated WebP container."""

    OUTPUT_FORMAT: str = WebP.OUTPUT_FORMAT
    OUTPUT_FORMAT_OBJ = Format(OUTPUT_FORMAT, False, True)
    PROGRAMS = ContainerHandler.init_programs(("webpmux", "img2webp"))
    _OPEN_WITH_PIL_FORMAT_OBJS = set([TIFF_ANIMATED_FORMAT_OBJ])
    _IMG2WEBP_ARGS_PREFIX = (PROGRAMS["img2webp"], "-min_size")
    _WEBPMUX_ARGS_PREFIX = (PROGRAMS["webpmux"], "-get", "frame")

    @classmethod
    def identify_format(cls, _path: Path) -> Optional[Format]:
        """Return the format if this handler can handle this path."""
        raise NotImplementedError()

    def _get_frame_path(self, frame_index: int) -> Path:
        """Return a frame path for an index."""
        return self.tmp_container_dir / f"frame-{frame_index:08d}.webp"

    def unpack_into(self) -> None:
        """Unpack webp into temp dir."""
        if self.input_format_obj in self._OPEN_WITH_PIL_FORMAT_OBJS:
            with Image.open(self.original_path) as image:
                frame_index = 0
                for frame in ImageSequence.Iterator(image):
                    frame_path = self._get_frame_path(frame_index)
                    frame.save(
                        frame_path,
                        self.OUTPUT_FORMAT,
                        lossless=True,
                        quality=100,
                        method=0,
                    )
                    frame_index += 1
            image.close()
        else:
            for frame_index in range(0, self.metadata.n_frames):
                frame_path = self._get_frame_path(frame_index)
                args = [
                    *self._WEBPMUX_ARGS_PREFIX,
                    str(frame_index),
                    str(self.original_path),
                    "-o",
                    str(frame_path),
                ]
                self.run_ext(tuple(args))

    def _prepare_metadata(self, data: Optional[bytes], working_path: Path, md_arg: str):
        """Prepare a metadata file and args for webpmux."""
        if not data:
            return []
        md_path = working_path.with_suffix("." + md_arg)
        with md_path.open("wb") as md_file:
            md_file.write(data)
        self.working_paths.add(md_path)
        return ["-set", md_arg, str(md_path)]

    def _set_metadata(self, working_path):
        """Set the exif data on the rebuilt image."""
        if not self.metadata.exif or self.metadata.icc_profile:
            return

        args = ["webpmux"]
        # dump exif
        if self.metadata.exif:
            args += self._prepare_metadata(self.metadata.exif, working_path, "exif")

        if self.metadata.icc_profile:
            args += self._prepare_metadata(
                self.metadata.icc_profile.encode(), working_path, "icc"
            )

        # move working file
        container_exif_working_path = self.get_working_path("exif")
        working_path.replace(container_exif_working_path)
        self.working_paths.add(container_exif_working_path)

        # run exif set
        args += [
            str(container_exif_working_path),
            "-o",
            str(working_path),
        ]
        self.run_ext(tuple(args))

    def pack_into(self, working_path: Path) -> None:
        """Remux the optimized frames into an animated webp."""
        frames = sorted([str(path) for path in self.tmp_container_dir.iterdir()])
        args = [
            *self._IMG2WEBP_ARGS_PREFIX,
            *frames,
            "-o",
            str(working_path),
        ]
        self.run_ext(tuple(args))
        if self.config.keep_metadata:
            self._set_metadata(working_path)
