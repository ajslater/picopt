"""Animated images are treated like containers."""
from abc import ABC
from pathlib import Path
from types import MappingProxyType
from typing import Any

from PIL import Image, ImageSequence
from PIL.PngImagePlugin import PngImageFile

from picopt.handlers.container import ContainerHandler
from picopt.handlers.handler import FileFormat


class ImageAnimated(ContainerHandler, ABC):
    """Animated image container."""

    PROGRAMS = (("pil2native",),)
    FRAME_PIL_FORMAT_STR = PngImageFile.format
    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType({})

    @classmethod
    def identify_format(cls, path: Path) -> FileFormat | None:  # noqa: ARG003
        """Return the format if this handler can handle this path."""
        return cls.OUTPUT_FILE_FORMAT

    def _get_frame_path(self, index: int, ext: str) -> Path:
        """Return a frame path for an index."""
        return self.tmp_container_dir / f"frame-{index:08d}.{ext}"

    def unpack_into(self) -> None:
        """Unpack webp into temp dir."""
        frame_index = 0
        frame_ext = self.FRAME_PIL_FORMAT_STR.lower()
        with Image.open(self.original_path) as image:
            for frame in ImageSequence.Iterator(image):
                frame_path = self._get_frame_path(frame_index, frame_ext)
                frame.save(
                    frame_path,
                    self.FRAME_PIL_FORMAT_STR,
                    compress_level=0,
                )
                frame_index += 1
        image.close()

    def pack_into(self, working_path: Path) -> None:
        """Remux the optimized frames into an animated webp."""
        # Collect frames
        frame_paths = sorted([str(path) for path in self.tmp_container_dir.iterdir()])
        head_frame_path = frame_paths[0]
        tail_frame_paths = frame_paths[1:]
        tail_frame_images = []
        for frame_path in tail_frame_paths:
            frame_image = Image.open(frame_path)
            tail_frame_images.append(frame_image)

        info = self.prepare_info(self.OUTPUT_FORMAT_STR)

        # Save Frames
        with Image.open(head_frame_path) as image:
            image.save(
                working_path,
                self.OUTPUT_FORMAT_STR,
                save_all=True,
                append_images=tail_frame_images,
                **self.PIL2_KWARGS,
                **info,
            )
