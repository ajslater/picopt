"""WebP Animated images are treated like containers."""
from pathlib import Path
from types import MappingProxyType

from PIL import Image, ImageSequence
from PIL.PngImagePlugin import PngImageFile

from picopt.handlers.container import ContainerHandler
from picopt.handlers.convertible import (
    APNG_FILE_FORMAT,
    CONVERTABLE_ANIMATED_FILE_FORMATS,
    CONVERTABLE_ANIMATED_FORMAT_STRS,
    GIF_FORMAT_STR,
    PNG_FORMAT_STR,
)
from picopt.handlers.gif import GifAnimated
from picopt.handlers.handler import FileFormat
from picopt.handlers.webp import WebPBase


class WebPAnimatedBase(ContainerHandler):
    """Animated WebP container."""

    OUTPUT_FORMAT_STR: str = WebPBase.OUTPUT_FORMAT_STR
    PROGRAMS = (("pil2native",),)
    PIL2_ARGS = MappingProxyType({"quality": 100, "method": 6, "minimize_size": True})

    @classmethod
    def identify_format(cls, path: Path) -> FileFormat | None:  # noqa: ARG003
        """Return the format if this handler can handle this path."""
        return cls.OUTPUT_FILE_FORMAT

    def _get_frame_path(self, frame_index: int) -> Path:
        """Return a frame path for an index."""
        return self.tmp_container_dir / f"frame-{frame_index:08d}.webp"

    def unpack_into(self) -> None:
        """Unpack webp into temp dir."""
        frame_index = 0
        with Image.open(self.original_path) as image:
            for frame in ImageSequence.Iterator(image):
                frame_path = self._get_frame_path(frame_index)
                frame.save(
                    frame_path,
                    PngImageFile.format,
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
                **self.PIL2_ARGS,
                **info,
            )


class WebPAnimatedLossless(WebPAnimatedBase):
    """Animated Lossless WebP Handler."""

    OUTPUT_FILE_FORMAT = FileFormat(WebPAnimatedBase.OUTPUT_FORMAT_STR, True, True)
    INPUT_FILE_FORMATS = frozenset(
        {OUTPUT_FILE_FORMAT, GifAnimated.OUTPUT_FILE_FORMAT, APNG_FILE_FORMAT}
        | CONVERTABLE_ANIMATED_FILE_FORMATS,
    )
    CONVERT_FROM_FORMAT_STRS = frozenset(
        CONVERTABLE_ANIMATED_FORMAT_STRS | {PNG_FORMAT_STR, GIF_FORMAT_STR}
    )
    PIL2_ARGS = MappingProxyType({**WebPAnimatedBase.PIL2_ARGS, "lossless": True})
